
odoo.define('tendercat.section_and_note_backend', function (require) {
// The goal of this file is to contain JS hacks related to allowing
// section, note and doc forms on tender proposals

"use strict";
var FieldChar = require('web.basic_fields').FieldChar;
var FieldOne2Many = require('web.relational_fields').FieldOne2Many;
var fieldRegistry = require('web.field_registry');
var ListFieldText = require('web.basic_fields').ListFieldText;
var ListRenderer = require('web.ListRenderer');
var ControlPanelView = require('web.ControlPanelView');
var Pager = require('web.Pager');

var ProposalDocsListRenderer = ListRenderer.extend({
    /**
     * We want section and note to take the whole line (except handle and trash)
     * to look better and to hide the unnecessary fields.
     *
     * @override
     */
    _renderBodyCell: function (record, node, index, options) {
        var $cell = this._super.apply(this, arguments);

        var isSection = record.data.display_type === 'line_section';
        var isNote = record.data.display_type === 'line_note';

        if (isSection || isNote) {
            if (node.attrs.widget === "handle") {
                return $cell;
            } else if (node.attrs.name === "name") {
                var nbrColumns = this._getNumberOfCols();
                if (this.handleField) {
                    nbrColumns--;
                }
                if (this.addTrashIcon) {
                    nbrColumns--;
                }
                $cell.attr('colspan', nbrColumns);
            } else {
                $cell.removeClass('o_invisible_modifier');
                return $cell.addClass('o_hidden');
            }
        }

        return $cell;
    },
    /**
     * We add the o_is_{display_type} class to allow custom behaviour both in JS and CSS.
     *
     * @override
     */
    _renderRow: function (record, index) {
        var $row = this._super.apply(this, arguments);

        if (record.data.display_type) {
            $row.addClass('o_is_' + record.data.display_type);
        }

        return $row;
    },
    /**
     * We want to add .o_section_and_note_list_view on the table to have stronger CSS.
     *
     * @override
     * @private
     */
    _renderView: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.$('.o_list_table').addClass('o_section_and_note_list_view');
        });
    }
});

// We create a custom widget because this is the cleanest way to do it:
// to be sure this custom code will only impact selected fields having the widget
// and not applied to any other existing ListRenderer.
var ProposalDocsFieldOne2Many = FieldOne2Many.extend({

    /**
     * We want to use our custom renderer for the list.
     *
     * @override
     */
    _getRenderer: function () {

        if (this.view.arch.tag === 'tree') {
            return ProposalDocsListRenderer;
        }
        return this._super.apply(this, arguments);
    },

    /**
     * Opens a FormViewDialog to allow creating a new record for a one2many.
     *
     * @override
     * @private
     * @param {OdooEvent|MouseEvent} ev this event comes either from the 'Add
     *   record' link in the list editable renderer, or from the 'Create' button
     *   in the kanban view
     * @param {Array} ev.data.context additional context for the added records,
     *   if several contexts are provided, multiple records will be added
     *   (form dialog will only use the context at index 0 if provided)
     * @param {boolean} ev.data.forceEditable this is used to bypass the dialog opening
     *   in case you want to add record(s) to a list
     * @param {function} ev.data.onSuccess called when the records are correctly created
     *   (not supported by form dialog)
     * @param {boolean} ev.data.allowWarning defines if the records can be added
     *   to the list even if warnings are triggered (e.g: stock warning for product availability)
     */
    // _onAddRecord: function (ev) {
    //     var self = this;
    //     var data = ev.data || {};
    //     var isSection = this.record.data.display_type === 'line_section';
    //     var isNote = this.record.data.display_type === 'line_note';
    //
    //     // we don't want interference with the components upstream.
    //     ev.stopPropagation();
    //
    //     if (this.editable || data.forceEditable) {
    //         if (!this.activeActions.create) {
    //             if (data.onFail) {
    //                 data.onFail();
    //             }
    //         } else if (!this.creatingRecord) {
    //             this.creatingRecord = true;
    //             this.trigger_up('edited_list', { id: this.value.id });
    //             this._setValue({
    //                 operation: 'CREATE',
    //                 position: this.editable || data.forceEditable,
    //                 context: data.context,
    //             }, {
    //                 allowWarning: data.allowWarning
    //             }).then(function () {
    //                 self.creatingRecord = false;
    //             }).then(function (){
    //                 if (data.onSuccess){
    //                     data.onSuccess();
    //                 }
    //             }).guardedCatch(function() {
    //                 self.creatingRecord = false;
    //             })
    //             ;
    //         }
    //     } else {
    //         // this._openFormDialog({
    //         //     context: data.context && data.context[0],
    //         //     on_saved: function (record) {
    //         //         self._setValue({ operation: 'ADD', id: record.id });
    //         //     },
    //         // });
    //
    //         // var context = data.context;
    //         // context.update({ 'display_type': this.record.data.display_type});
    //
    //         return this._rpc({
    //             model: 'tender_cat.tender.proposal.doc.line',
    //             method: 'get_formview_action',
    //             args: [[]],
    //             context: data.context && data.context[0],
    //         }).then(function(action) {
    //             return self.do_action(action);
    //         })
    //     }
    // },

    _onOpenRecord: function(ev) {
            var self = this;
            ev.stopPropagation();
            var id = ev.data.id;
            var record_id = parseInt(ev.target.allFieldWidgets[id][0].recordData.id)

            return this._rpc({
                model: 'tender_cat.tender.proposal.doc.line',
                method: 'get_formview_action',
                args: [record_id],
                context: this.record.getContext(this.recordParams),
            }).then(function(action) {
                return self.do_action(action);
            });

        },

});

// This is a merge between a FieldText and a FieldChar.
// We want a FieldChar for section,
// and a FieldText for the rest (product and note).
var ProposalDocsFieldText = function (parent, name, record, options) {
    var isSection = record.data.display_type === 'line_section';
    var Constructor = isSection ? FieldChar : ListFieldText;
    return new Constructor(parent, name, record, options);
};

// fieldRegistry.add('section_and_note_one2many', SectionAndNoteFieldOne2Many);
// fieldRegistry.add('section_and_note_text', SectionAndNoteFieldText);

fieldRegistry.add('proposal_docs_one2many', ProposalDocsFieldOne2Many);
fieldRegistry.add('proposal_docs_text', ProposalDocsFieldText);


return ProposalDocsListRenderer;
});
