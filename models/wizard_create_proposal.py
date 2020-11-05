# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import base64
from PyPDF2 import PdfFileWriter, PdfFileReader
import io

_logger = logging.getLogger(__name__)


class CreateProposalWizard(models.TransientModel):
    """
    Create proposal for tender
    """
    _name = 'tender_cat.create.proposal.wizard'
    _description = 'Create proposal for tender'

    tender_id = fields.Many2one('tender_cat.tender', string='Tender')
    proposal_template_id = fields.Many2one('tender_cat.tender.proposal.template', string='Proposal template')

    tender_desc = fields.Char(string='Tender description')
    tender_number = fields.Char(string='Tender')

    @api.model
    def default_get(self, default_fields):
        result = super(CreateProposalWizard, self).default_get(default_fields)

        if 'proposal_template_id' in default_fields:
            found_ids = self.env['tender_cat.tender.proposal.template'].search([], limit=1)
            if found_ids:
                result['proposal_template_id'] = found_ids[0].id

        active_id = self.env.context.get('active_id')
        if active_id:
            result['tender_id'] = active_id
            tender = self.env['tender_cat.tender'].browse(active_id)
            result['tender_desc'] = tender.full_name
            result['tender_number'] = tender.tender_id

        return result

    def action_create_proposal(self):

        return {
            'name': _('Create tender proposal'),
            'res_model': 'tender_cat.create.proposal.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('tender_cat.view_tender_cat_create_proposal_wizard_form').id,
            'context': self.env.context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def _create_proposal_doc_line(self, vals):
        doc_ids = {
            'doc_copy': 'doc_copy_id',
            'doc_report': 'doc_report_id',
            'doc_template': 'doc_template_id',
            'doc_external': 'doc_external_id',
        }
        # Clear all doc ids, excerpt selected one
        doc_class = vals.get('doc_class', '')
        for key, val in doc_ids.items():
            if not val == doc_ids[doc_class]:
                vals.update({val: 0})

        vals.update({'name': ''})

        # Copy file content
        if doc_class in ['doc_copy']:
            doc_id = vals[doc_ids[doc_class]]
            if doc_id:
                doc = self.env['tender_cat.tender.document'].browse(doc_id)
                if doc.file_content:
                    vals.update({'file_content': doc.file_content})

        new_line = self.env['tender_cat.tender.proposal.doc.line'].create(vals)
        new_line.document_id_change()
        new_line.set_desc()

    def create_proposal(self):

        new_proposal = self.env['tender_cat.tender.proposal'].create({
            'tender_id': self.tender_id.id,
            'name': _('Пропозиція для {}'.format(self.tender_id.tender_id)),
            'description': self.tender_id.full_name,
        })

        templ_label_docs = {}

        templ_lines = self.env['tender_cat.tender.proposal.template.line'].search([
            ('proposal_template_id', '=', self.proposal_template_id.id),
        ])

        def add_doc_line(lines_dct, lab_id, line_number, add_docs):
            if lab_id in lines_dct:
                lines_dct[lab_id]['order'] = min(templ_label_docs[lab_id]['order'], line_number)
                lines_dct[lab_id]['docs'].append({
                        'copy_id': add_docs[0],
                        'report_id': add_docs[1],
                        'template_id': add_docs[2],
                        'external_id': add_docs[3],
                        'doc_class': add_docs[4],
                    })
            else:
                lines_dct[lab_id] = {
                    'order': line_number,
                    'docs': [{
                        'copy_id': add_docs[0],
                        'report_id': add_docs[1],
                        'template_id': add_docs[2],
                        'external_id': add_docs[3],
                        'doc_class': add_docs[4],
                    }],
                }

        # Labels and documents from proposal template
        for line in templ_lines:
            line_num = int(line.line_number)
            docs = (line.doc_copy_id.id, line.doc_report_id.id, line.doc_template_id.id, line.doc_external_id.id,
                    line.doc_class)
            if line.label_ids:
                for label in line.label_ids:
                    add_doc_line(templ_label_docs, label.name, line_num, docs)
            else:
                empty = ''
                add_doc_line(templ_label_docs, empty, line_num, docs)

        # Labels from tender texts
        tender_labels = self.tender_id.get_text_labels()
        tender_label_names = [label['name'] for label in tender_labels]

        for label, vals in sorted(templ_label_docs.items(), key=lambda x: x[1]['order']):
            if label:
                if label in tender_label_names:
                    # Label from tender text, create section
                    self.env['tender_cat.tender.proposal.doc.line'].create({
                        'proposal_id': new_proposal.id,
                        'name': label,
                        'display_type': 'line_section',
                    })
                    for doc_ids in vals['docs']:
                        self._create_proposal_doc_line({
                            'proposal_id': new_proposal.id,
                            'name': '',
                            'display_type': '',
                            'doc_class': doc_ids['doc_class'],
                            'doc_copy_id': doc_ids['copy_id'],
                            'doc_report_id': doc_ids['report_id'],
                            'doc_template_id': doc_ids['template_id'],
                            'doc_external_id': doc_ids['external_id'],
                        })
            else:
                for doc_ids in vals['docs']:
                    self._create_proposal_doc_line({
                        'proposal_id': new_proposal.id,
                        'name': '',
                        'display_type': '',
                        'doc_class': doc_ids['doc_class'],
                        'doc_copy_id': doc_ids['copy_id'],
                        'doc_report_id': doc_ids['report_id'],
                        'doc_template_id': doc_ids['template_id'],
                        'doc_external_id': doc_ids['external_id'],
                    })

        # Add labels that found in tender text and not exist in proposal template
        # Add them as empty sections
        proposal_templ_labels = [key for key in templ_label_docs]
        for label in tender_label_names:
            if label not in proposal_templ_labels:
                # Add section and empty document string
                self.env['tender_cat.tender.proposal.doc.line'].create({
                    'proposal_id': new_proposal.id,
                    'name': label,
                    'display_type': 'line_section',
                })

                self.env['tender_cat.tender.proposal.doc.line'].create({
                    'proposal_id': new_proposal.id,
                    'display_type': '',
                    'name': _('Add documents to this section'),
                })

        return {
            'name': _('Create proposal'),
            'type': 'ir.actions.act_window',
            'res_model': 'tender_cat.tender.proposal',
            'view_mode': 'form',
            'res_id': new_proposal.id,
        }
