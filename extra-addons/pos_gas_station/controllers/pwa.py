# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class UtrecarPWAController(http.Controller):

    @http.route([
        '/manifest.json',
        '/manifest.webmanifest',
        '/pos_gas_station/manifest.webmanifest',
        '/web/manifest.webmanifest'
    ], type='http', auth='none', methods=['GET'], cors='*')
    def get_manifest(self, **kwargs):
        """Devuelve el manifiesto PWA oficial de Utrecar con alcance global."""
        manifest = {
            "name": "Utrecar TPV - Gasolineras",
            "short_name": "Utrecar",
            "description": "Terminal de Punto de Venta y Gestión de Estaciones de Servicio Utrecar",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#d97706",
            "orientation": "any",
            "icons": [
                {
                    "src": "/pos_gas_station/static/src/img/pwa/ronda_norte_icon_192.png",
                    "type": "image/png",
                    "sizes": "192x192",
                    "purpose": "any"
                },
                {
                    "src": "/pos_gas_station/static/src/img/pwa/ronda_norte_icon_512.png",
                    "type": "image/png",
                    "sizes": "512x512",
                    "purpose": "any maskable"
                }
            ],
            "screenshots": [
                {
                    "src": "/pos_gas_station/static/src/img/pwa/screenshot_mobile.png",
                    "sizes": "449x1024",
                    "type": "image/png"
                },
                {
                    "src": "/pos_gas_station/static/src/img/pwa/screenshot_desktop.png",
                    "sizes": "1024x576",
                    "type": "image/png",
                    "form_factor": "wide"
                }
            ]
        }
        return request.make_response(
            json.dumps(manifest),
            headers=[
                ('Content-Type', 'application/manifest+json; charset=utf-8'),
                ('Cache-Control', 'public, max-age=3600'),
                ('Access-Control-Allow-Origin', '*'),
            ]
        )

    @http.route([
        '/sw.js',
        '/pos_gas_station/sw.js'
    ], type='http', auth='none', methods=['GET'])
    def get_service_worker(self, **kwargs):
        """Devuelve el Service Worker de la PWA con alcance permitido en raíz '/'."""
        content = """const CACHE_NAME = 'utrecar-pos-pwa-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Permite que todas las peticiones a Odoo (JSON-RPC, Bus, WebSockets) fluyan con normalidad
});
"""
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'text/javascript; charset=utf-8'),
                ('Service-Worker-Allowed', '/'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ]
        )
