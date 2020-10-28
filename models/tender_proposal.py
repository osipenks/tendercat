# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _
import logging


_logger = logging.getLogger(__name__)


class TenderProposal(models.Model):
    _name = 'tender_cat.tender.proposal'
    _description = "Tender proposal"
    _inherit = 'mail.thread'

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    tender_id = fields.Many2one('tender_cat.tender', index=True, ondelete='cascade', string='Tender', required=True)

    doc_date = fields.Date(string='Date', default=fields.Date.today())

    user_id = fields.Many2one('res.users', string='Assigned to', default=lambda self: self.env.uid, index=True, tracking=True)

    doc_line_ids = fields.One2many(
        'tender_cat.tender.proposal.doc.line', 'proposal_id', string='Documents',
        copy=True)

    def add_section_control(self):
        doc_lines = []
        val = (0, 0, {
            'display_type': 'line_section',
            'name': 'SECTION NAME!!',
        })
        doc_lines.append(val)
        self.update({'doc_line_ids': doc_lines})

    def action_download_zip(self):
        # action = self.env.ref('tender_cat.tender_cat_data_models_action')
        # msg = _(
        #     "Fine, dude")
        # raise exceptions.RedirectWarning(msg, action.id, _("Go to the configuration panel"))
        # self.env.user.notify_default(message=_("Looks great, dude!"),
        #                              title='Download .zip',
        #                              sticky=False)

        raise exceptions.UserError("Everything Ok, downloaded!")

        # return {'warning': {
        #     'title': _("Download .zip"),
        #     'message': _("Everything Ok, downloaded!")
        # }}


class TenderProposalDocLine(models.Model):
    _name = 'tender_cat.tender.proposal.doc.line'
    _description = "Tender proposal document line"

    name = fields.Text(string='Description')

    sequence = fields.Integer('Sequence', default=1)
    line_number = fields.Integer(compute='_compute_get_number', store=True, )

    proposal_id = fields.Many2one('tender_cat.tender.proposal', 'Tender proposal', index=True, ondelete='cascade',
                                  required=True)

    document_id = fields.Many2one('tender_cat.tender.document', string='Document',
                                  change_default=True, ondelete='restrict')

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")

    _sql_constraints = [
        ('tender_proposal_required_fields',
         "CHECK(COALESCE(display_type IN ('line_section', 'line_note'), 'f') OR document_id IS NOT NULL)",
         "Missing required fields on proposal doc line."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(document_id=False)

            values.update(self._prepare_add_missing_fields(values))

        lines = super().create(vals_list)

        return lines

    @api.model
    def _prepare_add_missing_fields(self, values):
        return values
        """ Deduce missing required fields from the onchange """
        res = {}
        onchange_fields = ['name', ]
        if values.get('proposal_id') and values.get('document_id') and any(f not in values for f in onchange_fields):
            line = self.new(values)
            line.document_id_change()
            for field in onchange_fields:
                if field not in values:
                    res[field] = line._fields[field].convert_to_write(line[field], line)
        return res

    @api.onchange('document_id')
    def document_id_change(self):
        if not self.document_id:
            return
        vals = {}

        desc = ''
        if self.document_id.document_type_id:
            desc += '{}'.format(self.document_id.document_type_id.name)

        if self.document_id.doc_date:
            if desc:
                desc += ', '
            desc += 'дата {}'.format(self.document_id.doc_date)

        vals.update(name=desc)
        self.update(vals)
        result = {}
        return result

    @api.depends('sequence', 'proposal_id')
    def _compute_get_number(self):
        for proposal in self.mapped('proposal_id'):
            number = 1
            doc_lines = self.env['tender_cat.tender.proposal'].browse(proposal.id).doc_line_ids.sorted(
                'sequence')
            for line in doc_lines:
                if line.display_type in ['line_section', 'line_note']:
                    continue
                line.line_number = number
                number += 1

