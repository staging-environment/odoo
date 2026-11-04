/**
 * Utrecar PWA Installer & Service Worker Handler
 * Proporciona aviso interactivo y soporte de instalación PWA en escritorio y móviles.
 */
(function () {
    if (window.__UTRECAR_PWA_INITIALIZED__) {
        return;
    }
    window.__UTRECAR_PWA_INITIALIZED__ = true;

    let deferredPrompt = null;
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.userAgent.includes("Mac") && "ontouchend" in document);
    const isStandalone = window.navigator.standalone || window.matchMedia('(display-mode: standalone)').matches;

    // Si ya está ejecutándose como aplicación instalada, no mostrar banners
    if (isStandalone) {
        console.log('[PWA] Ejecutándose en modo Standalone (App instalada).');
        return;
    }

    // Registro del Service Worker en la raíz '/'
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
            navigator.serviceWorker.register('/sw.js', { scope: '/' })
                .then(function (reg) {
                    console.log('[PWA] Service Worker registrado para Utrecar con alcance:', reg.scope);
                })
                .catch(function (err) {
                    console.warn('[PWA] Error al registrar Service Worker:', err);
                });
        });
    }

    // Creación dinámica del banner flotante
    function createBanner() {
        let banner = document.getElementById('pwa-install-banner');
        if (banner) {
            return banner;
        }

        banner = document.createElement('div');
        banner.id = 'pwa-install-banner';
        banner.style.cssText = [
            'display: none',
            'position: fixed',
            'bottom: 24px',
            'left: 50%',
            'transform: translateX(-50%)',
            'width: calc(100% - 32px)',
            'max-width: 440px',
            'background: rgba(15, 23, 42, 0.95)',
            'backdrop-filter: blur(16px)',
            '-webkit-backdrop-filter: blur(16px)',
            'border: 1px solid rgba(217, 119, 6, 0.35)',
            'box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.5), 0 0 25px rgba(217, 119, 6, 0.2)',
            'padding: 14px 18px',
            'border-radius: 20px',
            'z-index: 9999999',
            'align-items: center',
            'justify-content: space-between',
            'gap: 14px',
            "font-family: 'Plus Jakarta Sans', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            'animation: pwaSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
        ].join(';');

        banner.innerHTML = `
            <style>
                @keyframes pwaSlideUp {
                    from { transform: translate(-50%, 50px); opacity: 0; }
                    to { transform: translate(-50%, 0); opacity: 1; }
                }
                #pwa-install-action-btn:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 6px 16px rgba(217, 119, 6, 0.5);
                }
                #pwa-install-close-btn:hover {
                    background: rgba(255, 255, 255, 0.16) !important;
                    color: #ffffff !important;
                }
            </style>
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
                <img src="/pos_gas_station/static/src/img/pwa/ronda_norte_icon_192.png" 
                     style="width: 44px; height: 44px; object-fit: contain; border-radius: 12px; flex-shrink: 0; border: 1px solid rgba(255,255,255,0.15);" 
                     alt="Utrecar" />
                <div style="min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <h4 style="margin: 0; font-size: 14px; font-weight: 800; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">Instalar Utrecar POS</h4>
                        <span style="background: rgba(217, 119, 6, 0.25); color: #fbbf24; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 6px; border: 1px solid rgba(217, 119, 6, 0.4);">App</span>
                    </div>
                    <p style="margin: 3px 0 0 0; font-size: 11.5px; color: #94a3b8; line-height: 1.3;">Instala la app en el escritorio o móvil para acceso rápido a pista.</p>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                <button id="pwa-install-action-btn" style="background: linear-gradient(135deg, #d97706 0%, #b45309 100%); color: white; border: none; font-size: 12.5px; font-weight: 700; padding: 9px 16px; border-radius: 12px; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; box-shadow: 0 4px 12px rgba(217, 119, 6, 0.4); white-space: nowrap;">
                    Instalar
                </button>
                <button id="pwa-install-close-btn" style="background: rgba(255, 255, 255, 0.08); border: none; color: #94a3b8; cursor: pointer; padding: 6px; border-radius: 10px; display: flex; align-items: center; justify-content: center; transition: background-color 0.2s;" aria-label="Cerrar">
                    <svg style="width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2.5;" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
        `;

        document.body.appendChild(banner);

        const installBtn = banner.querySelector('#pwa-install-action-btn');
        const closeBtn = banner.querySelector('#pwa-install-close-btn');

        installBtn.addEventListener('click', async function () {
            if (isIOS) {
                showIOSModal();
                return;
            }
            if (!deferredPrompt) {
                console.log('[PWA] No hay deferredPrompt disponible.');
                return;
            }
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            console.log('[PWA] Resultado de instalación:', outcome);
            deferredPrompt = null;
            banner.style.display = 'none';
        });

        closeBtn.addEventListener('click', function () {
            banner.style.display = 'none';
            sessionStorage.setItem('utrecar-pwa-dismissed', 'true');
        });

        return banner;
    }

    // Modal con instrucciones táctiles para iPhone / iPad Safari
    function showIOSModal() {
        let modal = document.getElementById('pwa-ios-instructions');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'pwa-ios-instructions';
            modal.style.cssText = [
                'display: flex',
                'position: fixed',
                'inset: 0',
                'background: rgba(0, 0, 0, 0.65)',
                'backdrop-filter: blur(6px)',
                '-webkit-backdrop-filter: blur(6px)',
                'z-index: 10000000',
                'justify-content: center',
                'align-items: flex-end',
                'padding: 16px',
                "font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"
            ].join(';');

            modal.innerHTML = `
                <div style="background: #ffffff; width: 100%; max-width: 400px; border-radius: 24px; padding: 24px; text-align: center; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); position: relative;">
                    <button id="pwa-ios-modal-close" style="position: absolute; top: 16px; right: 16px; background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px;">
                        <svg style="width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 2.5;" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                    <img src="/pos_gas_station/static/src/img/pwa/ronda_norte_icon_192.png" style="width: 56px; height: 56px; object-fit: contain; margin: 0 auto 14px auto; border-radius: 14px; display: block;" />
                    <h3 style="margin: 0 0 6px 0; font-size: 17px; font-weight: 800; color: #0f172a;">Instalar en iPhone o iPad</h3>
                    <p style="margin: 0 0 18px 0; font-size: 13px; color: #64748b; line-height: 1.4;">Añade el TPV de Utrecar a tu pantalla de inicio en dos pasos:</p>
                    <div style="display: flex; flex-direction: column; gap: 14px; text-align: left; margin-bottom: 22px;">
                        <div style="display: flex; align-items: flex-start; gap: 12px;">
                            <div style="background: #fef3c7; color: #d97706; font-weight: 800; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 12px;">1</div>
                            <div style="font-size: 13px; color: #334155; line-height: 1.4;">
                                Pulsa el botón de <strong>Compartir</strong> en la barra de Safari (<svg style="width: 15px; height: 15px; display: inline; vertical-align: middle; stroke: #007aff; fill: none; stroke-width: 2; margin: 0 2px;" viewBox="0 0 24 24"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg>).
                            </div>
                        </div>
                        <div style="display: flex; align-items: flex-start; gap: 12px;">
                            <div style="background: #fef3c7; color: #d97706; font-weight: 800; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 12px;">2</div>
                            <div style="font-size: 13px; color: #334155; line-height: 1.4;">
                                Desplázate hacia abajo y pulsa en <strong>"Añadir a la pantalla de inicio"</strong>.
                            </div>
                        </div>
                    </div>
                    <button id="pwa-ios-modal-ok" style="background: #d97706; color: white; border: none; width: 100%; font-size: 14px; font-weight: 700; padding: 12px; border-radius: 12px; cursor: pointer; transition: background-color 0.2s;">
                        Entendido
                    </button>
                </div>
            `;
            document.body.appendChild(modal);
            modal.querySelector('#pwa-ios-modal-close').addEventListener('click', () => modal.remove());
            modal.querySelector('#pwa-ios-modal-ok').addEventListener('click', () => modal.remove());
        } else {
            modal.style.display = 'flex';
        }
    }

    function showBanner() {
        if (sessionStorage.getItem('utrecar-pwa-dismissed')) {
            return;
        }
        if (document.body) {
            const banner = createBanner();
            banner.style.display = 'flex';
        } else {
            window.addEventListener('DOMContentLoaded', function () {
                const banner = createBanner();
                banner.style.display = 'flex';
            });
        }
    }

    // Interceptar el evento de instalación nativa en Chrome / Edge / Android
    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        console.log('[PWA] Evento beforeinstallprompt capturado con éxito.');
        showBanner();
    });

    // En iOS Safari no existe beforeinstallprompt, mostrar banner informativo si no es standalone
    if (isIOS && !isStandalone) {
        showBanner();
    }
})();
