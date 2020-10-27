# -*- coding: utf-8 -*-

from odoo import models, fields, api
from urllib.parse import urlparse
from . import tender_source
from . import text_pipe
from ..libcat.mytextpipe import mytextpipe
import os
import base64
import logging
import random
import csv


_logger = logging.getLogger(__name__)


class Tender(models.Model):
    _name = 'tender_cat.tender'
    _description = "Tender"
    _inherit = 'mail.thread'

    name = fields.Char(string='Name', track_visibility='onchange')
    full_name = fields.Char(string='Full name', track_visibility='onchange')
    value = fields.Float(string='Total budget')
    description = fields.Text(string='Detailed description')

    tender_id = fields.Char(string='Tender ID', copy=False, track_visibility='onchange',
                            help='The tender identifier to refer tender to in “paper” documentation.')

    procuring_entity_id = fields.Many2one(
        'res.partner', string='Procuring entity', help='Organization conducting the tender',
        required=False, change_default=True, index=True, track_visibility='onchange')

    tender_group_id = fields.Many2one('tender_cat.tender.group', string='Group', index=True)
    note = fields.Text(string='Note')

    auction_url = fields.Char(string='A URL for view auction')
    date = fields.Date(string='Date')

    tender_period_start = fields.Date(string='Begins', default=fields.Date.today())
    tender_period_end = fields.Date(string='Ends')

    doc_count = fields.Integer(compute='_compute_req_documents_count',
                               string="Number of required documents")
    req_count = fields.Integer()
    file_count = fields.Integer(compute='_compute_attached_file_count', string="Number of files attached")

    user_id = fields.Many2one('res.users',
                              string='Assigned to',
                              default=lambda self: self.env.uid,
                              index=True, tracking=True)

    is_filled = fields.Boolean(default=False)
    is_training_example = fields.Boolean(default=False)

    date_created = fields.Datetime(string='Created', readonly=True, default=lambda self: fields.Datetime.now())

    _order = 'date_created desc'

    def _compute_attached_file_count(self):
        attachment = self.env['ir.attachment']
        for tender in self:
            tender.file_count = attachment.search_count([
                '&',
                ('res_model', '=', 'tender_cat.tender'), ('res_id', '=', tender.id)
            ])

    def _compute_req_documents_count(self):
        query = """SELECT COUNT(DISTINCT sel.label_id) AS count
                        FROM
                            (SELECT 
                            tender_cat_file_chunk_tender_cat_label_rel.tender_cat_label_id AS label_id,
                            tender_cat_file_chunk.tender_id AS tender_id
                            FROM tender_cat_file_chunk_tender_cat_label_rel
                            LEFT JOIN tender_cat_file_chunk ON tender_cat_file_chunk.id = tender_cat_file_chunk_id
                            ) AS sel
                        WHERE   sel.tender_id = %s
                        """
        for tender in self:
            self.env.cr.execute(query, (tender.id, ))
            res = self.env.cr.dictfetchone()
            if res:
                tender.doc_count = res['count']

    @api.model
    def _get_processing_folder(self):
        return str(
            self.env["ir.config_parameter"]
                .sudo()
                .get_param("tender_cat.processing_folder", default='~/')
        )

    @api.model
    def _get_req_documents_data_model(self):
        return int(self.env['ir.config_parameter'].sudo().get_param('tender_cat.req_docs_data_model', default=0))

    def set_is_training_example(self):
        if self.is_training_example:
            vals = {'is_training_example': 0}
        else:
            vals = {'is_training_example': 1}
        self.write(vals)

    def file_tree_view(self):
        attachment_action = self.env.ref('base.action_attachment')
        action = attachment_action.read()[0]
        action['domain'] = str([
            '&',
            ('res_model', '=', 'tender_cat.tender'),
            ('res_id', 'in', self.ids)
        ])
        action['context'] = "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id)
        return action

    def texts_tree_view(self):

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tender_cat.file_chunk',
            'name': "Texts",
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'search_default_tender_id': self.id, 'search_default_doc_list': True},
        }

    def load_tender_files(self, tender_id=None):
        # Download tender data
        file_folder = os.path.join(self._get_processing_folder(), 'file')

        tender_src = tender_source.TenderSourceProzorroWeb(file_folder)
        tender_src.tender_files(self.tender_id)

        attachments = self.env['ir.attachment']
        corp = mytextpipe.corpus.FileCorpusReader(file_folder)

        tid = self.tender_id if tender_id is None else tender_id

        for abs_file_path in corp.docs(categories=[tid]):
            with open(abs_file_path, 'rb') as f:
                _, file_name = os.path.split(abs_file_path)

                attach_data = {
                    'name': file_name,
                    'datas': base64.b64encode(f.read()),
                    'type': 'binary',
                    'description': file_name,
                    'res_model': 'tender_cat.tender',
                    'res_id': self.id,
                }
                # todo: bug

                found_attachment = attachments.search(
                    ['&', ('name', '=', file_name), ('res_model', '=', 'tender_cat.tender'), ('res_id', '=', self.id)])
                if found_attachment:
                    found_attachment.write(attach_data)
                else:
                    attachments.create(attach_data)

    def get_tender_source(self):
        file_folder = os.path.join(self._get_processing_folder(), 'file')
        return tender_source.TenderSourceProzorroWeb(file_folder)

    def reload_tender_data(self):
        if self.tender_id:
            tender_src = self.get_tender_source()
            self.update_tender_fields(tender_src.tender_desc(self.tender_id))
            self.load_tender_files(self.tender_id)

    def mark_contexts(self, chunk_ids=None):
        """
        Mark neighbours of labeled chunks to show them when user views labeled texts with context
        """
        context_depth = 2

        chunks = self.env['tender_cat.file_chunk']
        if chunk_ids is None:
            chunk_ids = chunks.search([
                ('tender_id', '=', self.id),
                ('user_label_ids', '!=', False),
            ]).ids

        for chunk in chunks.browse(chunk_ids):
            try:
                chunk_number = int(chunk.chunk_id)
            except ValueError:
                continue
            bottom = max(0, chunk_number - context_depth)
            top = chunk_number + context_depth + 1
            for chunk_id in range(bottom, top):
                found_chunk = chunks.search([
                    ('chunk_id', '=', chunk_id),
                    ('tender_file_id', '=', chunk.tender_file_id.id),
                    ('is_doc_context', '!=', True),
                ])
                if found_chunk:
                    found_chunk.write({'is_doc_context': True})

    def _get_request_file(self):
        """
        Dump tender texts with features to csv
        """
        processing_folder = os.path.join(self._get_processing_folder(), 'tmp')
        query_pid = str(random.randint(0, 999))

        # ../789_request.csv
        csv_name = os.path.join(processing_folder, query_pid + '_request.csv')

        # 1. Dump tender texts to request csv
        chunks = self.env['tender_cat.file_chunk']
        chunk_ids = chunks.search([('tender_id', '=', self.id)]).ids

        with open(csv_name, mode='w') as f:
            csv_fields = ['id', 'text', 'file', 'category', 'label', 'score']
            writer = csv.DictWriter(f, fieldnames=csv_fields, delimiter=',')
            writer.writeheader()
            for chunk in chunks.browse(chunk_ids):
                writer.writerow({
                    'id': chunk.id,
                    'text': chunk.chunk_text,
                    'file': chunk.tender_file_id.id,
                    'category': self.id,
                    'label': '',
                    'score': 0.0
                })
            f.close()

        return csv_name

    def _process_response_file(self, response_path):
        """
        Process transformer's response csv file
        """
        chunks = self.env['tender_cat.file_chunk']
        chunk_ids = chunks.search([('tender_id', '=', self.id)]).ids
        labels = self.env['tender_cat.label']

        threshold = 0.05

        if not os.path.isfile(response_path):
            return

        with open(response_path, mode='r') as f:
            reader = csv.DictReader(f)
            for line in reader:
                chunk_id = int(line['id'])
                score_val = float(line['score'])
                is_req_doc = True if score_val > threshold else False
                label_id = line['label']

                for chunk in chunks.browse(chunk_id):
                    if not chunk:
                        continue

                    if is_req_doc and label_id:
                        labels_ids = labels.search([('id', '=', label_id)]).ids
                        chunk.write({
                            'req_doc_score': score_val,
                            'is_req_doc': is_req_doc,
                            'user_label_ids': [(4, labels_ids[0])]
                        })
                    else:
                        chunk.write({'req_doc_score': score_val, 'is_req_doc': is_req_doc, })

    def mark_required_docs(self):
        """
        Iterate through tender chunks and calculate similarities to sentences of model dataset If average similarity
        is above 0.7 (??) mark chunk as document
        """
        data_model = self.env['tender_cat.data.model'].browse(self._get_req_documents_data_model())
        if data_model:
            data_model.transform_data(self.id)

        # Delete files

    def make_assessment(self):

        # todo: check if we need 1 and 2, if files not changed since last conversion
        # 1. Delete old text chunks
        query = 'DELETE FROM tender_cat_file_chunk WHERE tender_id = {}'.format(self.id)
        self.env.cr.execute(query)

        # 2. All files from attachments convert to html
        file_dir = os.path.join(self._get_processing_folder(), 'file')
        html_dir = os.path.join(self._get_processing_folder(), 'html')

        text_pipe.prozorro_file_to_html([self.tender_id], file_dir, html_dir)

        # 3. Each html split in to sentences and write to DB as file chunks
        corp = mytextpipe.corpus.HTMLCorpusReader(root=html_dir, clean_text=True, language='russian')

        files = self.env['ir.attachment']
        file_ids = files.search([
            ('res_model', '=', 'tender_cat.tender'),
            ('res_id', '=', self.id),
        ]).ids

        for file in files.browse(file_ids):
            file_name, _ = os.path.splitext(os.path.basename(file.name))
            doc_id = os.path.join(self.tender_id, file_name + '.html')
            chunk_cnt = 1
            for sent in corp.sents(ids=doc_id):
                chunk_id = chunk_cnt
                self.env['tender_cat.file_chunk'].create({
                    'tender_id': self.id,
                    'chunk_text': sent,
                    'tender_file_id': file.id,
                    'chunk_id': chunk_id,
                    'name': chunk_id
                })
                chunk_cnt += 1

        # 4. Find all types of required documents
        self.mark_required_docs()

        # 5. Calculate stats and mark contexts for new labeled chunks
        self.mark_contexts()

    def update_tender_fields(self, tender_data):
        for key, val in tender_data.items():
            if not val:
                continue
            if key == 'value':
                self.value = float(val.replace(',', '.'))
            if key == 'description':
                self.description = val
            if key == 'header':
                self.full_name = val
            if key == 'tender_id':
                self.tender_id = val
                self.name = val
            if key == 'auction_url':
                self.auction_url = val
            if key == 'procuring_entity_name':
                pass
            if key == 'procuring_entity_id':
                pass

    @api.onchange('tender_id')
    def _onchange_tender(self):

        # User may enter url or tender ID, we need to get right tender ID here
        if self.tender_id:
            parse_res = urlparse(self.tender_id)
            path_list = parse_res.path.split('/')
            if path_list:
                self.tender_id = path_list[-1]

        if self.tender_id:
            tender_src = self.get_tender_source()
            # Construct tender link
            if parse_res.netloc:
                self.auction_url = parse_res.geturl()
            else:
                self.auction_url = tender_src.tender_url(self.tender_id)

            if not self.is_filled:
                # Update tender fields
                self.update_tender_fields(tender_src.tender_desc(self.tender_id))
        else:
            self.auction_url = ''

    @api.model_create_multi
    def create(self, vals_list):

        for values in vals_list:
            values['is_filled'] = (self.full_name or self.description)
            values['date_created'] = fields.Datetime.now()
            if 'tender_id' in values:
                values['name'] = values['tender_id']

        res = super(Tender, self).create(vals_list)

        for values in vals_list:
            tender_id = values.get('tender_id')
            if tender_id:
                res.load_tender_files(tender_id)

        return res

    def write(self, vals):

        vals['is_filled'] = (self.full_name or self.description)
        if 'tender_id' in vals:
            vals['name'] = vals['tender_id']

        res = super(Tender, self).write(vals) if vals else True
        return res


class TenderFile(models.Model):
    _name = 'tender_cat.file'
    _description = 'Tender file'
    _inherit = 'ir.attachment'

    tender_id = fields.Many2one('tender_cat.tender', ondelete='cascade',
                                string='Assigned to',
                                index=True)
    req_docs_score = fields.Integer()

