from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Buku Perpustakaan'

    title = fields.Char(string='Judul', required=True)
    category = fields.Selection([
        ('umum', 'Umum'),
        ('it', 'IT'),
        ('kesehatan', 'Kesehatan'),
        ('politik', 'Politik'),
    ], string='Kategori')
    publication_date = fields.Date(string='Tanggal Terbit')
    author_ids = fields.Many2many('library.author', string='Penulis')
    isbn_code = fields.Char(string='Kode ISBN', required=True)
    available_quantity = fields.Integer(string='Jumlah Tersedia')

    def name_get(self):
        result = []
        for record in self:
            name = record.title or 'Unnamed'
            result.append((record.id, name))
        return result
        
class LibraryMember(models.Model):
    _name = 'library.member'
    _description = 'Model Member'

    name = fields.Char(string='Nama Member', required=True)
    identity_number = fields.Char(string='No Identitas', required=True, unique=True)
    id_card_type = fields.Selection([
        ('ktp', 'KTP'),
        ('sim', 'SIM'),
        ('pasport', 'Pasport')
    ], string='Jenis Kartu Identitas', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved')
    ], string='State', default='draft')

class LibraryRentalTransaction(models.Model):
    _name = 'library.rental.transaction'
    _description = 'Transaksi Rental'

    rental_date = fields.Date(string='Tanggal Rental', required=True)
    borrower_id = fields.Many2one('library.member', string='Nama Peminjam', required=True)
    transaction_status = fields.Selection([
        ('ongoing', 'Sedang Dipinjam'),
        ('not_returned', 'Belum Dikembalikan'),
        ('completed', 'Selesai'),
    ], string='Status Transaksi', required=True, default='ongoing')
    borrowed_books = fields.One2many('library.borrowed.book', 'rental_id', string='Buku yang Dipinjam')
    total_rental_cost = fields.Float(string='Total Biaya Sewa', compute='_compute_total_rental_cost')

    @api.depends('borrowed_books.total_rental_cost') 
    def _compute_total_rental_cost(self):
        for transaction in self:
            total_cost = sum(borrowed_book.total_rental_cost for borrowed_book in transaction.borrowed_books)
            transaction.total_rental_cost = total_cost
            
    @api.depends('borrowed_books.total_rental_cost')
    def _compute_total_rental_cost(self):
        for record in self:
            record.total_rental_cost = sum(record.borrowed_books.mapped('total_rental_cost'))
            
    @api.model
    def create(self, vals):

        transaction = super(LibraryRentalTransaction, self).create(vals)

        for borrowed_book in transaction.borrowed_books:
            book = borrowed_book.book_id
            if book.available_quantity < borrowed_book.quantity_borrowed:
                raise ValidationError(
                    f'Jumlah yang dipinjam ({borrowed_book.quantity_borrowed}) melebihi stok tersedia ({book.available_quantity}) untuk buku {book.title}.'
                )
            book.available_quantity -= borrowed_book.quantity_borrowed

        return transaction

    def action_return_books(self):
        for transaction in self:
            for borrowed_book in transaction.borrowed_books:
                borrowed_book.book_id.available_quantity += borrowed_book.quantity_borrowed
            transaction.transaction_status = 'completed'

class LibraryAuthor(models.Model):
    _name = 'library.author'
    _description = 'Penulis'

    name = fields.Char(string='Nama Penulis', required=True)
    identity_number = fields.Char(string='No Identitas')
    id_card_type = fields.Selection([('KTP', 'KTP'), ('SIM', 'SIM'), ('Pasport', 'Pasport')], string='Jenis Kartu Identitas')
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved')], string='State', default='draft')

    @api.model
    def action_view_books(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Buku oleh Penulis',
            'res_model': 'library.book',
            'view_mode': 'tree,form',
            'domain': [('author_ids', 'in', self.id)],
        }

class LibraryBorrowedBook(models.Model):
    _name = 'library.borrowed.book'
    _description = 'List Buku yang Dipinjam'

    rental_id = fields.Many2one('library.rental.transaction', string='Transaksi Rental', ondelete='cascade')
    book_id = fields.Many2one('library.book', string='Buku', required=True)
    location = fields.Char(string='Lokasi')
    quantity_borrowed = fields.Integer(string='Jumlah Buku yang Dipinjam', required=True)
    start_date = fields.Date(string='Tanggal Mulai', required=True)
    end_date = fields.Date(string='Tanggal Selesai')
    total_rental_cost = fields.Float(string='Total Biaya Sewa')
    returned = fields.Boolean(string='Pengembalian?')

    @api.constrains('quantity_borrowed', 'book_id')
    def _check_stock_availability(self):
        for record in self:
            book = record.book_id
            available_stock = book.available_quantity

            if record.quantity_borrowed > available_stock:
                raise ValidationError(
                    f'Jumlah yang dipinjam ({record.quantity_borrowed}) melebihi stok tersedia ({available_stock}) untuk buku {book.title}.'
                )

class RentalReportWizard(models.TransientModel):
    _name = 'rental.report.wizard'
    _description = 'Rental Report Wizard'

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    borrower_ids = fields.Many2many('res.partner', string='Borrowers')

    def action_generate_report(self):
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'borrower_ids': self.borrower_ids.ids,
        }
        return self.env.ref('your_module_name.action_rental_report').report_action(self, data=data)