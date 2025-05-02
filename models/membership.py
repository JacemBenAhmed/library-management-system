from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError


class Membership(models.Model):
    """
    Modèle représentant l'adhésion dans la bibliothèque.
    Hérite des fonctionnalités de suivi d'activité et de messagerie d'Odoo.
    """

    _name = 'library.membership'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'ref'

    membership_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('semestry', 'Semestry'),
        ('yearly', 'Yearly')],
        default="monthly"
    )
    membership_number = fields.Integer()
    renewal_amount = fields.Integer()
    active = fields.Boolean('Active', default=1)
    states = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired')],
        default='draft'
    )
    expiry_date = fields.Date()
    expiry_email = fields.Boolean()
    member_id = fields.Many2one('res.partner', required=True)
    ref = fields.Char(default="New", readonly=True)
    membership_number_readonly = fields.Integer()

    @api.onchange('membership_type')
    def _compute_renewal_amount(self):
        """
        Calcule le montant de renouvellement et la date d'expiration
        en fonction du type d'adhésion sélectionné.
        """

        renewal_amount_monthly = int(self.env['ir.config_parameter'].get_param('My_Library.renewal_amount_monthly', 0))
        renewal_amount_semestry = int(self.env['ir.config_parameter'].get_param('My_Library.renewal_amount_semestry', 0))
        renewal_amount_yearly = int(self.env['ir.config_parameter'].get_param('My_Library.renewal_amount_yearly', 0))

        for rec in self:
            member = rec.member_id
            base_date = member.expiry_date if member.expiry_date and member.expiry_date > fields.Date.today() else fields.Date.today()

            if rec.membership_type == 'monthly':
                rec.renewal_amount = renewal_amount_monthly
                rec.expiry_date = base_date + timedelta(days=30)
            elif rec.membership_type == 'semestry':
                rec.renewal_amount = renewal_amount_semestry
                rec.expiry_date = base_date + timedelta(days=180)
            else:
                rec.renewal_amount = renewal_amount_yearly
                rec.expiry_date = base_date + timedelta(days=360)

            member.expiry_date = rec.expiry_date

    def membership_states_cron(self):
        """
        Cron job pour expirer les adhésions arrivées à échéance.
        """

        for rec in self.search([]):
            if rec.states == 'active' and rec.expiry_date and fields.Date.today() > rec.expiry_date:
                rec.states = 'expired'
                rec.active = False
                rec.member_id.states = 'terminated'

    def action_renew_membership(self):
        """
        Renouvelle l'adhésion du membre si aucune autre adhésion active n'existe.
        """

        count = self.search_count([
            ('member_id', '=', self.member_id.id),
            ('id', '!=', self.id),
            ('states', '=', 'active')
        ])

        if count > 0:
            raise ValidationError("This Member Already Has An Active Membership.")
        else:
            self.states = 'active'
            self.member_id.states = 'active'
            self.member_id.expiry_date = self.expiry_date
            self.member_id.membership_number = self.membership_number
            self.member_id.expiry_email = self.expiry_email

    @api.constrains('member_id', 'membership_number')
    def check_member_membership_number(self):
        """
        S'assure que le numéro d'adhésion est unique par membre.
        """

        for rec in self:
            existing = self.search([
                ('id', '!=', rec.id),
                '|',
                '&', ('member_id', '=', rec.member_id.id), ('membership_number', '!=', rec.membership_number),
                '&', ('member_id', '!=', rec.member_id.id), ('membership_number', '=', rec.membership_number),
            ])
            if existing:
                raise ValidationError('Invalid or Duplicate Membership Number.')

    @api.model_create_multi
    def create(self, vals):
        """
        Génère une référence automatique si définie à 'New'.
        """

        records = super(Membership, self).create(vals)
        for rec in records:
            if rec.ref == 'New':
                rec.ref = self.env['ir.sequence'].next_by_code('membership-seq')
        return records
