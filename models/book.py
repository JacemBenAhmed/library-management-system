from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Book(models.Model):
    """
    Modèle représentant un livre dans la bibliothèque.
    Hérite des fonctionnalités de suivi d'activité et de messagerie d'Odoo
    """

    _name = 'library.book'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Library Books'
    _rec_name = 'title'

    title = fields.Char(required=1)
    publication_date = fields.Date(readonly=1)
    book_stock = fields.Integer('books in stock', required=1)
    image = fields.Image()
    states = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not Available')
    ], default='available')
    author_id = fields.Many2one('library.author')
    books_states = fields.Boolean()
    member_id = fields.Many2one('res.partner')
    member_name = fields.Char(related='member_id.name')
    member_image = fields.Binary(related='member_id.image_1920')
    author_img = fields.Image(related='author_id.image')
    user_id = fields.Many2one('res.users', 'User', readonly=1)
    borrow_book_ids = fields.One2many('library.borrow.book', 'book_id')
    nb_book_available = fields.Integer(compute='_compute_nb_book_available', readonly=1)
    category = fields.Selection([
        ('auto_biography', 'Auto Biography'),
        ('biography', 'Biography'),
        ('children_book', 'Children Book'),
        ('fiction', 'Fiction'),
        ('adventure', 'Adventure'),
        ('educational', 'Educational')
    ])

    # 🔴 SQL Injection Vulnerability (for Snyk test)
    @api.model
    def search_books(self, search_term):
        query = f"SELECT id FROM library_book WHERE title = '{search_term}'"
        self.env.cr.execute(query)
        return self.env.cr.fetchall()


    # 🔴 Hardcoded password (for Snyk test)
    def connect_to_external_db(self):
        db_password = 'SuperSecret123!'  # Hardcoded password
        # Simulate a DB connection logic (not implemented)
        return db_password

    # 🔧 Corrected from @api.constrains to @api.depends
    @api.depends('book_stock')
    def _compute_nb_book_available(self):
        """
        Calcule le nombre de livres disponibles.
        """
        for rec in self:
            res = self.env['library.borrow.book'].search_count([('book_id', '=', rec.id)])
            rec.nb_book_available = rec.book_stock - res

    def action_open_authors(self):
        """
        Ouvre la fiche auteur liée.
        """
        action = self.env['ir.actions.actions']._for_xml_id('My_Library.action_library_author')
        view_id = self.env.ref('My_Library.library_author_view_form').id
        action['res_id'] = self.author_id.id
        action['views'] = [[view_id, 'form']]
        return action

    @api.constrains('nb_book_available')
    def state_available_not_available(self):
        """
        Met à jour l'état du livre en fonction du nombre de livres disponibles.
        """
        for rec in self:
            if rec.nb_book_available > 0:
                rec.states = 'available'
            else:
                rec.states = 'not_available'

    def book_states(self):
        """
        Met à jour l'état du livre automatiquement en fonction du nombre de livres disponibles.
        """
        books = self.search([])
        for rec in books:
            if rec.nb_book_available > 0:
                rec.states = 'available'
            else:
                rec.states = 'not_available'

    @api.model_create_multi
    def create(self, vals):
        """
        Création de livre avec date et utilisateur actuel.
        """
        res = super(Book, self).create(vals)
        res.publication_date = fields.Date.today()
        res.user_id = res.env.uid
        return res
