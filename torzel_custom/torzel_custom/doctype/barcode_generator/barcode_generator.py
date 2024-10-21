# Copyright (c) 2024, V12 Infotech and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document

class BarcodeGenerator(Document):
    def before_submit(self):
        # Set the barcode field to the document name if it is not already set
        if not self.barcode:
            self.barcode = self.name

    def on_submit(self):
        # Create a Stock Entry when Barcode Generator is submitted
        stock_entry = frappe.get_doc({
            'doctype': 'Stock Entry',
            'naming_series':'BAR-.YYYY.-',
            'stock_entry_type': 'Repack',  # Or appropriate type
            'items': self.get_items(),  # Implement get_items() to extract items from Barcode Generator
            'posting_date': frappe.utils.nowdate()
        })
        stock_entry.insert()
        stock_entry.submit()

        # Link the Stock Entry to the Barcode Generator
        self.db_set('auto_stock_entry_number', stock_entry.name)

    def on_cancel(self):
        # Cancel the linked Stock Entry if the Barcode Generator is canceled
        if self.auto_stock_entry_number:
            stock_entry = frappe.get_doc('Stock Entry', self.auto_stock_entry_number)
            if stock_entry.docstatus == 1:  # If it's submitted, cancel it
                stock_entry.cancel()
            else:
                stock_entry.delete()

    def get_items(self):
        print("Barcode Items", self)
        net_weight_diff_defaults = self.get_default_warehouse('net_weight_diff')
        tare_weight_diff_defaults = self.get_default_warehouse('tare_weight_diff')
        final_net_weight = self.net_weight

        # Extract items using dispatched weights
        items = [
            {
                'item_code': self.raw_material,
                'qty': self.net_weight,  # Use Dispatched Net Weight
                's_warehouse': self.source_warehouse,
                't_warehouse': None,
            },
        ]
        
         # Add Net Weight Difference item if applicable
        if self.net_weight_diff != 0:
            final_net_weight = final_net_weight + self.net_weight_diff
            items.append({
                'item_code': 'net_weight_diff',
                'qty': abs(self.net_weight_diff),
                's_warehouse': net_weight_diff_defaults['source_warehouse'] if self.net_weight_diff > 0 else None,
                't_warehouse': None if self.net_weight_diff > 0 else net_weight_diff_defaults['target_warehouse']
            })

        # Add Tare Weight Difference item if applicable
        if self.tare_weight_diff != 0:
            final_net_weight = final_net_weight + self.tare_weight_diff
            items.append({
                'item_code': 'tare_weight_diff',
                'qty': abs(self.tare_weight_diff),
                's_warehouse': tare_weight_diff_defaults['source_warehouse'] if self.tare_weight_diff > 0 else None,
                't_warehouse': None if self.tare_weight_diff > 0 else tare_weight_diff_defaults['target_warehouse']
            })
            
        items.append({
                'item_code': self.finished_product,
                'qty': final_net_weight,  # Use Dispatched Net Weight
                's_warehouse': None,
                't_warehouse': self.target_warehouse,
        })
          
        return items
    
    
    def get_default_warehouse(self, item_code):
        """
        Fetch the default warehouse for a given item from Item Default table.
        Returns a dictionary with 'source_warehouse' and 'target_warehouse'.
        """
        item_defaults = frappe.db.get_value('Item Default', {'parent': item_code}, 
                                            ['default_warehouse'], as_dict=True)

        if not item_defaults or not item_defaults.default_warehouse:
            frappe.throw(f"Default Warehouse not found for item {item_code}")

        # Return the default warehouse as both source and target (customize as needed)
        return {
            'source_warehouse': item_defaults.default_warehouse,
            'target_warehouse': item_defaults.default_warehouse
        }
    

