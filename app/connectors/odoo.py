"""Restricted Odoo JSON-2 adapter for inventory and draft purchase orders."""
from urllib.parse import urlsplit

import httpx


class OdooError(Exception):
    pass


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    local_http = parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}
    if (parsed.scheme != 'https' and not local_http) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Odoo URL must use HTTPS (HTTP is allowed for localhost only).')
    return value.rstrip('/')


class OdooClient:
    def __init__(self, base_url: str, api_key: str, database: str | None = None):
        self.base_url = validate_base_url(base_url)
        if not api_key:
            raise ValueError('Odoo API key is required.')
        self.headers = {'Authorization': f'bearer {api_key}', 'Content-Type': 'application/json'}
        if database:
            self.headers['X-Odoo-Database'] = database

    def call(self, model: str, method: str, arguments: dict):
        try:
            response = httpx.post(
                f'{self.base_url}/json/2/{model}/{method}',
                headers=self.headers,
                json=arguments,
                timeout=20,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise OdooError('Could not reach the configured Odoo server.') from exc
        if response.is_error:
            raise OdooError(f'Odoo returned HTTP {response.status_code}.')
        try:
            return response.json()
        except ValueError as exc:
            raise OdooError('Odoo returned a non-JSON response.') from exc

    def test(self):
        result = self.call('res.users', 'context_get', {})
        if not isinstance(result, dict):
            raise OdooError('Odoo connection check returned an unexpected response.')
        return {'status': 'connected'}

    def stock_levels(self, product_code: str | None = None, limit: int = 100):
        domain = [['quantity', '>', 0]]
        if product_code:
            domain.append(['product_id.default_code', '=', product_code])
        records = self.call('stock.quant', 'search_read', {
            'domain': domain,
            'fields': ['product_id', 'location_id', 'quantity', 'reserved_quantity', 'available_quantity'],
            'limit': limit,
        })
        if not isinstance(records, list):
            raise OdooError('Odoo returned an unexpected stock response.')
        return {
            'records': records,
            'count': len(records),
            'product_code': product_code,
            'quantity_available': sum(float(item.get('available_quantity') or 0) for item in records) if product_code else None,
            'note': 'Odoo stock data; physical stock is not independently verified.',
        }

    def purchase_orders(self, limit: int = 50):
        records = self.call('purchase.order', 'search_read', {
            'domain': [['state', 'in', ['draft', 'sent', 'to approve', 'purchase']]],
            'fields': ['name', 'partner_id', 'date_order', 'state', 'amount_total', 'currency_id'],
            'limit': limit,
            'order': 'date_order desc',
        })
        if not isinstance(records, list):
            raise OdooError('Odoo returned an unexpected purchase-order response.')
        return {'records': records, 'count': len(records)}

    def create_draft_purchase_order(self, vendor_id: int, lines: list[dict], reference: str | None = None):
        if reference:
            existing = self.call('purchase.order', 'search_read', {
                'domain': [['origin', '=', reference]],
                'fields': ['name', 'partner_id', 'state', 'amount_total', 'origin'],
                'limit': 1,
            })
            if isinstance(existing, list) and existing:
                return {'record': existing[0], 'note': 'Existing draft returned for this Kanca task step; no duplicate was created.'}
        order_lines = [[0, 0, {
            'product_id': item['product_id'],
            'product_qty': item['quantity'],
            'price_unit': item.get('price_unit', 0),
        }] for item in lines]
        order_id = self.call('purchase.order', 'create', {
            'partner_id': vendor_id,
            'order_line': order_lines,
            **({'origin': reference} if reference else {}),
        })
        if type(order_id) is not int:
            raise OdooError('Odoo did not return the created purchase-order ID.')
        records = self.call('purchase.order', 'read', {
            'ids': [order_id],
            'fields': ['name', 'partner_id', 'state', 'amount_total'],
        })
        if not isinstance(records, list) or len(records) != 1:
            raise OdooError('Odoo created the draft but could not return its details.')
        return {'record': records[0], 'note': 'Draft only; it has not been confirmed in Odoo.'}

    def update_draft_purchase_order_note(self, order_id: int, note: str):
        records = self.call('purchase.order', 'read', {'ids': [order_id], 'fields': ['state', 'name']})
        if not isinstance(records, list) or len(records) != 1 or records[0].get('state') != 'draft':
            raise ValueError('Only an existing draft purchase order can be changed.')
        self.call('purchase.order', 'write', {'ids': [order_id], 'vals': {'notes': note}})
        return {'id': order_id, 'name': records[0].get('name'), 'updated': True, 'state': 'draft'}
