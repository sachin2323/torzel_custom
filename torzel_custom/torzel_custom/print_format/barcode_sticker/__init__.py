import frappe

def execute(filters=None):
    # Define the SQL queries for CPA13 and IL4 separately

    # CPA13 Query
    cpa13_query = """
    WITH Opening_Balance AS (
        SELECT 
            SUM(
                CASE 
                    WHEN gle.is_opening = "Yes" THEN gle.debit - gle.credit
                    WHEN gle.is_opening = "No" AND gle.posting_date < %(from_date)s THEN gle.debit - gle.credit
                    ELSE 0
                END
            ) AS opening_balance
        FROM 
            `tabGL Entry` gle
        LEFT JOIN
            `tabJournal Entry` je ON gle.voucher_no = je.name AND gle.voucher_type = 'Journal Entry'
        WHERE 
            gle.is_cancelled = 0
            AND gle.party = %(party)s
            AND (je.is_system_generated IS NULL OR je.is_system_generated = 0)
    ),
    GL_Transactions AS (
        SELECT
            gl.posting_date,
            gl.voucher_type,
            gl.voucher_no,
            FORMAT(gl.debit, 2) AS debit,
            FORMAT(gl.credit, 2) AS credit,
            NULL AS item_code,
            NULL AS quantity,
            NULL AS rate
        FROM
            `tabGL Entry` gl
        WHERE
            ((gl.party = %(party)s AND gl.party_type = 'Customer')
            OR (gl.party = %(party)s AND gl.party_type = 'Supplier'))
            AND gl.posting_date >= %(from_date)s
            AND gl.is_cancelled = 0
            AND gl.is_opening = "No"
    ),
    Inventory_Details AS (
        SELECT
            si.posting_date,
            'Sales Invoice' AS voucher_type,
            si.name AS voucher_no,
            NULL AS debit,
            NULL AS credit,
            sii.item_code,
            sii.qty AS quantity,
            sii.rate
        FROM
            `tabSales Invoice` si
        JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        WHERE
            si.customer = %(party)s
            AND si.posting_date >= %(from_date)s
            AND si.docstatus < 2

        UNION ALL

        SELECT
            pi.posting_date,
            'Purchase Invoice' AS voucher_type,
            pi.name AS voucher_no,
            NULL AS debit,
            NULL AS credit,
            pii.item_code,
            pii.qty AS quantity,
            pii.rate
        FROM
            `tabPurchase Invoice` pi
        JOIN
            `tabPurchase Invoice Item` pii ON pi.name = pii.parent
        WHERE
            pi.supplier = %(party)s
            AND pi.posting_date >= %(from_date)s
            AND pi.docstatus < 2
    )

    SELECT
        NULL AS posting_date,
        'Opening Balance' AS voucher_type,
        NULL AS voucher_no,
        FORMAT(opening_balance, 2) AS debit,
        0 AS credit,
        NULL AS item_code,
        NULL AS quantity,
        NULL AS rate
    FROM
        Opening_Balance

    UNION ALL

    SELECT
        posting_date,
        voucher_type,
        voucher_no,
        debit,
        credit,
        item_code,
        quantity,
        rate
    FROM (
        SELECT * FROM GL_Transactions
        UNION ALL
        SELECT * FROM Inventory_Details
    ) AS combined_entries

    ORDER BY
        posting_date ASC, voucher_no ASC, item_code ASC;
    """

    # IL4 Query
    il4_query = """
    WITH Opening_Balance AS (
        SELECT 
            SUM(
                CASE 
                    WHEN gle.is_opening = "Yes" THEN gle.debit - gle.credit
                    WHEN gle.is_opening = "No" AND gle.posting_date < %(from_date)s THEN gle.debit - gle.credit
                    ELSE 0
                END
            ) AS opening_balance
        FROM 
            `tabGL Entry` gle
        LEFT JOIN
            `tabJournal Entry` je ON gle.voucher_no = je.name AND gle.voucher_type = 'Journal Entry'
        WHERE 
            gle.is_cancelled = 0
            AND gle.party = %(party)s
            AND (je.is_system_generated IS NULL OR je.is_system_generated = 0)
    ),
    Inventory_Details AS (
        SELECT
            si.posting_date,
            'Sales Invoice' AS voucher_type,
            si.name AS voucher_no,
            NULL AS inward_quantity,
            sii.qty AS outward_quantity,
            sii.item_code
        FROM
            `tabSales Invoice` si
        JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        WHERE
            si.customer = %(party)s
            AND si.posting_date >= %(from_date)s
            AND si.docstatus < 2

        UNION ALL

        SELECT
            pi.posting_date,
            'Purchase Invoice' AS voucher_type,
            pi.name AS voucher_no,
            pii.qty AS inward_quantity,
            NULL AS outward_quantity,
            pii.item_code
        FROM
            `tabPurchase Invoice` pi
        JOIN
            `tabPurchase Invoice Item` pii ON pi.name = pii.parent
        WHERE
            pi.supplier = %(party)s
            AND pi.posting_date >= %(from_date)s
            AND pi.docstatus < 2
    )

    SELECT
        posting_date,
        voucher_type,
        voucher_no,
        inward_quantity,
        outward_quantity,
        item_code
    FROM (
        SELECT * FROM Inventory_Details
    ) AS combined_entries
    WHERE 
        inward_quantity IS NOT NULL OR outward_quantity IS NOT NULL
    ORDER BY
        posting_date ASC, voucher_no ASC, item_code ASC;
    """

    # Execute CPA13 Query
    cpa13_data = frappe.db.sql(cpa13_query, filters, as_dict=True)

    # Execute IL4 Query
    il4_data = frappe.db.sql(il4_query, filters, as_dict=True)

    # Define columns for the combined report
    columns = [
        {"fieldname": "posting_date", "label": "Posting Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "voucher_type", "label": "Voucher Type", "fieldtype": "Data", "width": 120},
        {"fieldname": "voucher_no", "label": "Voucher No", "fieldtype": "Data", "width": 100},
        {"fieldname": "debit", "label": "Debit", "fieldtype": "Currency", "width": 100},
        {"fieldname": "credit", "label": "Credit", "fieldtype": "Currency", "width": 100},
        {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Data", "width": 100},
        {"fieldname": "quantity", "label": "Quantity", "fieldtype": "Float", "width": 80},
        {"fieldname": "rate", "label": "Rate", "fieldtype": "Currency", "width": 100},
        {"fieldname": "inward_quantity", "label": "Inward Quantity", "fieldtype": "Float", "width": 80},
        {"fieldname": "outward_quantity", "label": "Outward Quantity", "fieldtype": "Float", "width": 80}
    ]

    # Add section headers for CPA13 and IL4
    combined_data = []
    combined_data.append({"posting_date": "CPA13 Report"})
    combined_data.extend(cpa13_data)
    combined_data.append({"posting_date": "IL4 Report"})
    combined_data.extend(il4_data)

    return columns, combined_data