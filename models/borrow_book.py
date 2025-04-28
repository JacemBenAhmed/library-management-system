from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BorrowBook(models.Model):
    """
            Modèle représentant l'emprunt de livres dans la bibliothèque.
            Hérite des fonctionnalités de suivi d'activité et de messagerie d'Odoo
    """

    _name = 'library.borrow.book'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Library borrow Book'
    _rec_name = 'ref'

    isbn = fields.Integer('ISBN', required=1)
    ref = fields.Char(default="New", readonly=1)
    book_id = fields.Many2one('library.book', required=1)
    members_id = fields.Many2one('res.partner', required=1)
    user_id = fields.Many2one('res.users', 'User', readonly=1)
    date_from = fields.Date()
    date_to = fields.Date()
    active = fields.Boolean('Active', default=1)
    return_date = fields.Date(readonly=1)
    nb_borrowed_day = fields.Integer(compute='_compute_nb_borrowed_day', readonly=1)
    states = fields.Selection([('draft', 'Draft'), ('borrowed', 'Borrowed'), ('overdue', 'Overdue'), ('returned', 'Returned')], default="draft")
    isbn_repetitions = fields.Integer(default=0)
    book_image = fields.Image(related='book_id.image')
    # book_available = fields.Integer(related='book_id.nb_book_available')
    member_email = fields.Char(related='members_id.email', readonly=1)
    # member_membership_number = fields.Integer(related='members_id.membership_number', readonly=1)
    members_image = fields.Binary(string='Member Image', related='members_id.image_1920')

    def _compute_nb_borrowed_day(self):
        """
               Calcule le nombre de jours d'emprunt pour chaque enregistrement.
               Le calcul est basé sur les dates 'date_from' et 'date_to' ou la date de retour si disponible
        """

        for rec in self:
            if not rec.return_date:
                if rec.date_from:
                    rec.nb_borrowed_day = (rec.date_to - rec.date_from).days
                else:
                    rec.nb_borrowed_day = 0
            else:
                rec.nb_borrowed_day = (rec.return_date - rec.date_from).days

    def action_borrow_book(self):
        """
                Action qui effectue l'emprunt du livre.
                Met à jour l'état du livre et réduit le nombre de livres disponibles
        """

        for rec in self:
            if rec.book_id.nb_book_available > 0:
                rec.book_id.member_id = rec.members_id
                rec.members_id.book_ids += rec.book_id
                rec.book_id.nb_book_available -= 1
                rec.states = 'borrowed'


    def action_return_book(self):
        """
                Action qui gère le retour du livre emprunté.
                Remet à jour le stock de livres disponibles et change l'état de l'emprunt à 'returned'
        """

        for rec in self:
            rec.book_id.member_id -= rec.members_id
            rec.members_id.book_ids -= rec.book_id
            rec.book_id.nb_book_available += 1
            rec.states = 'returned'
            rec.active = False
            rec.members_id.states = 'active'
            rec.return_date = fields.Date.today()



    @api.constrains('date_to', 'date_from')
    def validate_date_from_to(self):
        """
                Contrainte de validation des dates 'date_from' et 'date_to'.
                Assure que les dates sont correctement configurées et logiques.
        """

        for res in self:
            if res.date_from and fields.Date.today() > res.date_from:
                raise ValidationError("Borrow Date Must Be Greater Then Today Date")
            elif res.date_to and res.date_from and res.date_from > res.date_to:
                raise ValidationError("Date To Must Be Greater Then Borrow Date")
            elif not res.date_to and not res.date_from:
                raise ValidationError("Please Add a Borrow Date And Date To")
            elif not res.date_from:
                raise ValidationError("Please Add a Borrow Date")
            elif res.date_to:
                return res
            else:
                raise ValidationError("Please Add a Date To")




    @api.model_create_multi
    def create(self, vals):
        """
                Méthode de création personnalisée pour l'emprunt de livres.
                Vérifie la validité de l'ISBN et du titre du livre avant de créer l'enregistrement
        """

        res = super(BorrowBook, self).create(vals)
        res.user_id = res.env.uid
        title_repetitions = 0
        books = self.search([])
        for book in books:
            if book.isbn == res.isbn:
                res.isbn_repetitions += 1
            if book.book_id.title == res.book_id.title:
                title_repetitions += 1
        if res.isbn_repetitions > 1 and title_repetitions > 1:
            raise ValidationError('the book is already borrowed')
        elif res.isbn_repetitions > 1 and title_repetitions == 1:
            raise ValidationError('the isbn is not valid')
        elif res.ref == 'New':
            res.ref = self.env['ir.sequence'].next_by_code('borrow-seq')
            return res

    def states_overdue(self):
        """
                Action pour vérifier les emprunts dépassés et mettre à jour leur état à 'overdue'
                """

        book = self.search([])
        for rec in book:
            if rec.states == 'borrowed':
                if fields.Date.today() > rec.date_to:
                    rec.states = 'overdue'
