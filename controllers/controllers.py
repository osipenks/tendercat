# -*- coding: utf-8 -*-
# from odoo import http


# class TenderCat(http.Controller):
#     @http.route('/tender_cat/tender_cat/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/tender_cat/tender_cat/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('tender_cat.listing', {
#             'root': '/tender_cat/tender_cat',
#             'objects': http.request.env['tender_cat.tender_cat'].search([]),
#         })

#     @http.route('/tender_cat/tender_cat/objects/<model("tender_cat.tender_cat"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('tender_cat.object', {
#             'object': obj
#         })
