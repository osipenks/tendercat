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

    doc_line_ids = fields.One2many('tender_cat.tender.proposal.doc.line', 'proposal_id', string='Documents', copy=True)

    _order = 'doc_date desc'

    def add_section_control(self):
        doc_lines = []
        val = (0, 0, {
            'display_type': 'line_section',
            'name': _('Section name'),
        })
        doc_lines.append(val)
        self.update({'doc_line_ids': doc_lines})


class TenderProposalDocLine(models.Model):
    _name = 'tender_cat.tender.proposal.doc.line'
    _description = "Tender proposal document line"

    name = fields.Text(string='Description')

    sequence = fields.Integer('Sequence', default=1)
    line_number = fields.Integer(compute='_compute_get_number', store=True, )

    proposal_id = fields.Many2one('tender_cat.tender.proposal', 'Tender proposal', index=True, ondelete='cascade',
                                  required=True)

    doc_class = fields.Selection([
        ('doc_copy', _('Copy of document')),
        ('doc_report', _('Report')),
        ('doc_template', _('Custom template')),
        ('doc_external', _('External document')),
    ], string='Document class', default='doc_copy')

    doc_repr = fields.Char(string='Document')
    doc_desc = fields.Char(string='Description')

    doc_copy_id = fields.Many2one('tender_cat.tender.document', string='Document')
    doc_report_id = fields.Many2one('tender_cat.tender.doc.report', string='Document')
    doc_template_id = fields.Many2one('tender_cat.tender.doc.template', string='Document')
    doc_external_id = fields.Many2one('tender_cat.tender.doc.external', string='Document')

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")

    file_content = fields.Binary('PDF')

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            values.update(self._prepare_add_missing_fields(values))
        lines = super().create(vals_list)
        return lines

    @api.model
    def _prepare_add_missing_fields(self, values):
        return values
        """ Deduce missing required fields from the onchange """
        res = {}
        onchange_fields = ['name', ]
        if values.get('proposal_id') and any(f not in values for f in onchange_fields):
            line = self.new(values)
            for field in onchange_fields:
                if field not in values:
                    res[field] = line._fields[field].convert_to_write(line[field], line)
        return res

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

    def get_view_id(self):
        res = False
        if self.id:
            if self.display_type in ['line_section', 'line_note']:
                return res
            if self.doc_class in ['doc_copy']:
                return self.env.ref('tender_cat.proposal_doc_line_doc_copy_form').id
        return res

    def get_formview_id(self, access_uid=None):
        formview_id = self.get_view_id()
        return formview_id if formview_id else super(TenderProposalDocLine, self).get_formview_id(access_uid=access_uid)

    def get_formview_action(self, access_uid=None):
        res = super(TenderProposalDocLine, self).get_formview_action(access_uid=access_uid)
        return res

    def unlink(self):
        for rec in self:
            number = 1
            doc_lines = self.env['tender_cat.tender.proposal'].browse(rec.proposal_id.id).doc_line_ids.sorted(
                'sequence')
            for line in doc_lines:
                if line.id == rec.id:
                    continue
                if line.display_type in ['line_section', 'line_note']:
                    continue
                line.line_number = number
                number += 1
        super(TenderProposalDocLine, self).unlink()

    def _get_active_doc(self, doc_ids=None):
        """
        Return correct class document-object for selected doc_class.
        Argument doc_ids:dict may contain 'doc_copy_id', 'doc_report_id' etc from write() method
        """
        doc_dct = {
            'doc_class': self.doc_class if doc_ids is None else
            doc_ids.get('doc_class', self.doc_class),
            'doc_copy': self.doc_copy_id.id if doc_ids is None else
            doc_ids.get('doc_copy_id', self.doc_copy_id.id),
            'doc_report': self.doc_report_id.id if doc_ids is None else
            doc_ids.get('doc_report_id', self.doc_report_id.id),
            'doc_template': self.doc_template_id.id if doc_ids is None else
            doc_ids.get('doc_template_id', self.doc_template_id.id),
            'doc_external': self.doc_external_id.id if doc_ids is None else
            doc_ids.get('doc_external_id', self.doc_external_id.id),
            }

        mods = {'doc_copy': 'tender_cat.tender.document',
                'doc_report': 'tender_cat.tender.doc.report',
                'doc_template': 'tender_cat.tender.doc.template',
                'doc_external': 'tender_cat.tender.doc.external',
                }

        doc_class = doc_dct.get('doc_class', False)

        return self.env[mods[doc_class]].browse(doc_dct[doc_class])

    def _get_doc_repr(self, doc_ids=None):
        active_doc_id = self._get_active_doc(doc_ids)
        return active_doc_id.name if active_doc_id else ''

    def _get_doc_desc(self, doc_ids=None):
        active_doc_id = self._get_active_doc(doc_ids)
        return active_doc_id.get_desc() if active_doc_id else ''

    def write(self, vals):
        # Clear file content, if it isn't doc_copy
        display_type = vals.get('display_type', 0)
        if display_type in ['line_section', 'line_note']:
            vals.update({'file_content': False})

        # Change line representation, if needed
        new_repr = False
        for key in vals:
            if key in ['doc_class', 'doc_copy_id', 'doc_report_id', 'doc_template_id', 'doc_external_id']:
                new_repr = self._get_doc_repr(vals)
                break
        if new_repr:
            vals.update({'doc_repr': new_repr})

        return super(TenderProposalDocLine, self).write(vals) if vals else True

    @api.onchange('doc_class', 'doc_copy_id', 'doc_report_id', 'doc_template_id', 'doc_external_id')
    def set_desc(self):
        self.name = self._get_doc_desc()
        self.doc_repr = self._get_doc_repr()


