# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from erpnext.utilities.transaction_base import TransactionBase


class StockReservationEntry(TransactionBase):
	def validate(self):
		from erpnext.stock.utils import validate_disabled_warehouse, validate_warehouse_company

		self.validate_posting_time()
		self.validate_mandatory()
		validate_disabled_warehouse(self.warehouse)
		validate_warehouse_company(self.warehouse, self.company)

	def on_submit(self):
		self.update_reserved_qty_in_voucher()
		self.update_status()

	def on_cancel(self):
		self.update_reserved_qty_in_voucher()
		self.update_status()

	def validate_mandatory(self):
		mandatory = [
			"item_code",
			"warehouse",
			"posting_date",
			"posting_time",
			"voucher_type",
			"voucher_no",
			"voucher_detail_no",
			"available_qty",
			"voucher_qty",
			"stock_uom",
			"reserved_qty",
			"company",
		]
		for d in mandatory:
			if not self.get(d):
				frappe.throw(_("{0} is required").format(self.meta.get_label(d)))

	def update_status(self, status=None, update_modified=True):
		if not status:
			if self.docstatus == 2:
				status = "Cancelled"
			elif self.reserved_qty == self.delivered_qty:
				status = "Delivered"
			elif self.delivered_qty and self.reserved_qty > self.delivered_qty:
				status = "Partially Delivered"
			elif self.docstatus == 1:
				status = "Reserved"
			else:
				status = "Draft"

		frappe.db.set_value(self.doctype, self.name, "status", status, update_modified=update_modified)

	def update_reserved_qty_in_voucher(self, update_modified=True):
		from frappe.query_builder.functions import Sum

		sre = frappe.qb.DocType("Stock Reservation Entry")
		reserved_qty = (
			frappe.qb.from_(sre)
			.select(Sum(sre.reserved_qty))
			.where(
				(sre.docstatus == 1)
				& (sre.voucher_type == self.voucher_type)
				& (sre.voucher_no == self.voucher_no)
				& (sre.voucher_detail_no == self.voucher_detail_no)
			)
		).run(as_list=True)[0][0] or 0

		frappe.db.set_value(
			"Sales Order Item",
			self.voucher_detail_no,
			"stock_reserved_qty",
			reserved_qty,
			update_modified=update_modified,
		)
