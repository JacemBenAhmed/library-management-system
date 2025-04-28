from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Members(models.Model):
    """
            Modèle pour gérer les membres de la bibliothèque
            Hérite du modèle 'res.partner' pour ajouter des fonctionnalités spécifiques aux membres, telles que la gestion des emprunts de livres
    """

    _inherit = 'res.partner'

    book_ids = fields.One2many('library.book', 'member_id')
    borrowed_book_ids = fields.One2many('library.borrow.book', 'members_id')
    user_id = fields.Many2one('res.users', 'User', readonly=1)
    membership_id = fields.Many2one('library.membership')
    membership_number = fields.Integer(readonly=1)
    expiry_date = fields.Date(readonly=1)
    expiry_email = fields.Boolean()

    nb_of_borrowed_book = fields.Integer(compute='_compute_nb_of_borrowed_book')
    nb_days_late = fields.Integer(readonly=1)

    states = fields.Selection(
        [('blocked', 'Blocked'), ('active', 'Membership Active'), ('terminated', 'Membership Terminated')],
        default='blocked')
    mail_date_to = fields.Date()
    mail_book_title = fields.Char()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    delay_penalty = fields.Monetary(readonly=1)

    @api.depends('borrowed_book_ids')
    def _compute_nb_of_borrowed_book(self):
        """
                Calcule le nombre total de livres empruntés par le membre
                Prend en compte que les emprunts qui sont  à l'état 'borrowed'
        """

        for rec in self:
            if rec.borrowed_book_ids:
                for book in rec.borrowed_book_ids:
                    if book.states != 'draft':
                        rec.nb_of_borrowed_book = self.env['library.borrow.book'].search_count(
                            [('members_id', '=', rec.id)])
                    else:
                        rec.nb_of_borrowed_book += 0
            else:
                rec.nb_of_borrowed_book += 0

    @api.depends('nb_days_late')
    def delay_penaltys(self):
        """
                Calcule la pénalité de retard pour chaque membre en fonction du nombre de jours de retard
                Utilise le taux d'amende journalière configuré dans les paramètres de l'application
        """

        daily_fine_rate = self.env['ir.config_parameter'].get_param('My_Library.daily_fine_rate')
        members = self.search([])
        for rec in members:
            rec.delay_penalty = int(daily_fine_rate) * rec.nb_days_late

    def action_delay_penalty(self):
        """
                        Cron action qui Calcule la pénalité de retard pour chaque membre de façon automatique chaque jour
                        Utilise le taux d'amende journalière configuré dans les paramètres de l'application
        """

        daily_fine_rate = self.env['ir.config_parameter'].get_param('My_Library.daily_fine_rate')
        members = self.search([])
        for rec in members:
            rec.delay_penalty = int(daily_fine_rate) * rec.nb_days_late

    def action_block_member(self):
        for rec in self:
            rec.states = 'blocked'

    def action_unblock_member(self):
        for rec in self:
            if rec.membership_id.states == 'active':
                rec.states = 'active'
            else:
                rec.states = 'terminated'

    def send_mail(self):
        """
               Envoie un email de rappel aux membres dont les livres empruntés doivent être retournés dans un jour
               Le modèle d'email utilisé est 'member_mail_template'
        """

        template = self.env.ref("My_Library.member_mail_template")
        members = self.search([])
        for rec in members:
            if rec.borrowed_book_ids:
                for book in rec.borrowed_book_ids:
                    if book.date_to and book.date_to < fields.Date.today():
                        day = (fields.Date.today() - book.date_to).days
                        if day == 1:
                            if rec.email:
                                rec.mail_date_to = book.date_to
                                rec.mail_book_title = book.book_id.title
                                template.send_mail(rec.id, force_send=True)

    def fct_nb_days_late(self):
        """
                Calcule le nombre de jours de retard pour chaque livre emprunté par un membre
                et met à jour la pénalité de retard
        """

        daily_fine_rate = self.env['ir.config_parameter'].get_param('My_Library.daily_fine_rate')
        members = self.search([])
        for rec in members:
            if rec.borrowed_book_ids:
                for book in rec.borrowed_book_ids:
                    if book.states != 'draft':
                        if book.date_to < fields.Date.today():
                            if not book.return_date:
                                rec.nb_days_late += (fields.Date.today() - book.date_to).days
                                rec.delay_penalty = int(daily_fine_rate) * rec.nb_days_late
                            else:
                                rec.nb_days_late += (book.return_date - book.date_to).days
                                rec.delay_penalty = int(daily_fine_rate) * rec.nb_days_late

                        else:
                            rec.nb_days_late += 0
                            rec.delay_penalty += 0

                    else:
                        rec.nb_days_late += 0
                        rec.delay_penalty += 0
            else:
                rec.nb_days_late += 0
                rec.delay_penalty += 0

    def member_block(self):
        """Cron action qui bloque un membre, empêchant toute nouvelle activité jusqu'à ce qu'il soit débloqué"""

        members = self.search([])
        for member in members:
            if member.nb_days_late > 0:
                member.states = 'blocked'
            else:
                member.states = 'active'

    def action_open_borrowed_book(self):
        """
             Ouvre la vue des livres empruntés pour un membre spécifique
             Permet de voir tous les emprunts en cours pour ce membre
        """

        return {
            'type': 'ir.actions.act_window',
            'name': 'Borrowed Book',
            'res_model': 'library.borrow.book',
            'domain': [('members_id', '=', self.id)],
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'create': False, 'edit': False, 'delete': False, 'archive': False},
        }

    def action_open_membership(self):
        """
               Ouvre la vue de gestion des adhésions pour le membre.
               Permet de gérer ou consulter l'adhésion actuelle du membre.
        """

        return {
            'type': 'ir.actions.act_window',
            'name': 'Membership',
            'res_model': 'library.membership',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def member_membership_states(self):
        """
                Met à jour l'état de l'adhésion des membres en fonction de la date d'expiration """

        members = self.search([])
        for rec in members:
            if rec.expiry_date and rec.expiry_date > fields.date.today():
                rec.states = 'active'
            elif rec.expiry_date and rec.expiry_date < fields.date.today():
                rec.states = 'terminated'
            else:
                rec.states = 'blocked'

    @api.model_create_multi
    def create(self, vals):
        """Crée un nouveau membre et assigne l'utilisateur actuel comme propriétaire """

        res = super(Members, self).create(vals)
        res.user_id = res.env.uid
        return res

    def penalty_mail(self):
        """
                Envoie un email de pénalité aux membres qui ont dépassé le nombre de jours de retard configuré
                """
        template = self.env.ref("My_Library.penalty_mail_template")
        penalty_days_mail = self.env['ir.config_parameter'].get_param('My_Library.penalty_days_mail')
        members = self.search([])
        for rec in members:
            if rec.borrowed_book_ids:
                if rec.nb_days_late > int(penalty_days_mail):
                    if rec.email:
                        template.send_mail(rec.id, force_send=True)

    def membership_terminated(self):
        """
               Envoie un email d'adhésion terminée aux membres dont l'adhésion a expiré
               Utilise le modèle 'membership_terminated_mail_template'
        """

        template = self.env.ref("My_Library.membership_terminated_mail_template")
        members = self.search([])
        for rec in members:
            print(rec.expiry_email)
            print(rec.expiry_date)
            print(rec.email)
            print(rec.membership_id)
            if rec.email and rec.expiry_email and fields.date.today() < rec.expiry_date:
                print("hello")
                day = (rec.expiry_date - fields.Date.today()).days
                if day == 1:
                    template.send_mail(rec.id, force_send=True)
