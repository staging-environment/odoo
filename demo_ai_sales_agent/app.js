// UTRECAR AI SDR - INTERACTIVE ENGINE
document.addEventListener('DOMContentLoaded', () => {
  // --- Data Store ---
  const companyData = {
    clima: {
      name: "Climatizaciones Guadalquivir SL",
      sector: "Climatización, Frío Industrial y SAT",
      employees: 28,
      location: "Sevilla (Polígono Calonge)",
      contact: "Manuel Rivas",
      role: "Director de Operaciones",
      email: "manuel.rivas@climagualdaquivir.es",
      phone: "+34 954 81 29 00",
      pain: "28 técnicos en furgonetas sin fichar o con papel arrugado; riesgo de sanciones en inspección.",
      solution: "App móvil con geofencing ligero al inicio de jornada y tablet quiosco en almacén.",
      mrr: 70.00,
      emailSubject: "Control horario y partes de trabajo de Climatizaciones Guadalquivir (evitar sanciones ITSS)",
      emailBody: `Hola Manuel,

Te contacto directamente porque veo que en Climatizaciones Guadalquivir contáis con cerca de 30 técnicos desplazados a diario por toda la provincia.

Con el endurecimiento de la Inspección de Trabajo respecto al registro digital de jornada y control de horas extras (RD-ley 8/2019), la mayoría de empresas de instalaciones sufren el mismo cuello de botella: partes en papel que se pierden, horas mal computadas y la incertidumbre de no saber si la inspección considerará válidos los registros.

En Utrecar hemos desarrollado una solución específica para equipos técnicos en calle:
• Fichaje en 2 segundos desde el móvil con geolocalización o tablet quiosco en vuestro almacén.
• Asignación automática de partes de trabajo y cuadrantes de guardias/horas extras.
• Descarga directa de informes trazables con 1 clic para la asesoría laboral o el inspector.

Para 28 técnicos, el coste es de solo 2,50 €/mes por empleado (unos 70 €/mes en total).

¿Te parecería bien que te active un acceso de prueba gratuito de 14 días para que lo testéis con 2 o 3 técnicos sin compromiso, o prefieres una demo de 10 min por videollamada?`,
      waBody: `Hola Manuel, te contacto de Utrecar Soluciones Digitales. Vemos que en Climatizaciones Guadalquivir tenéis un equipo técnico importante en ruta. Para evitar problemas con la Inspección de Trabajo en el registro diario de jornada y horas extras, hemos lanzado una app donde los operarios fichan en 2 segundos desde el móvil con geolocalización o tablet en almacén. Cuesta solo 2,50€/técnico al mes y te ahorra horas de papeleo. ¿Te paso un enlace para probarlo 14 días gratis sin compromiso?`
    },

    gastro: {
      name: "Grupo Restauración Al-Andalus",
      sector: "Hostelería & Restauración (3 locales)",
      employees: 52,
      location: "Sevilla & Aljarafe",
      contact: "Elena Vega",
      role: "Gerente y Responsable de Personal",
      email: "elena.vega@alandalusgastro.com",
      phone: "+34 955 12 34 56",
      pain: "Turnos partidos, cambios constantes entre personal de sala y cocina, inspecciones nocturnas.",
      solution: "Tablet quiosco con PIN/reconocimiento facial en barra y app para intercambiar turnos.",
      mrr: 130.00,
      emailSubject: "Gestión de turnos rotativos y registro de jornada sin papel en Grupo Al-Andalus",
      emailBody: `Hola Elena,

Te escribo porque en el sector de la restauración en Sevilla, gestionar los turnos partidos de sala y cocina sin volverse loco con los cuadrantes y las inspecciones sorpresa de trabajo es un reto diario.

Con más de 50 empleados entre vuestros locales, nuestro sistema de Control Horario y Gestión de Personal os permite:
• Fichaje instantáneo en barra o cocina con tablet quiosco (por PIN o QR), sin que los camareros necesiten usar su móvil personal.
• Planificación visual de cuadrantes de turnos rotativos y festivos trabajados.
• Registro 100% legal e inalterable exigido por la Inspección de Trabajo para evitar sanciones de hasta 7.500€.

El coste para vuestro volumen es de 2,50 €/empleado al mes.

¿Te vendría bien que te prepare un acceso demo de 14 días para uno de vuestros locales y así veis lo ágil que resulta?`,
      waBody: `Hola Elena, enhorabuena por el crecimiento de Grupo Al-Andalus. Te escribo de Utrecar. Sabemos el dolor de cabeza que suponen los turnos rotativos y el registro horario en hostelería ante una inspección. Tenemos un sistema con tablet en barra donde la plantilla ficha por PIN en 1 segundo y los cuadrantes se sincronizan solos. ¿Te gustaría probarlo 14 días gratis en uno de los restaurantes?`
    },

    logistica: {
      name: "Trans-Utrera Distribuciones",
      sector: "Transporte de mercancías y paquetería",
      employees: 19,
      location: "Utrera (Polígono El Torno)",
      contact: "Joaquín Benítez",
      role: "Jefe de Flota y Tráfico",
      email: "jbenitez@transutrera.es",
      phone: "+34 955 86 11 22",
      pain: "Conductores que inician jornada directamente en ruta; necesidad de justificar horas de presencia vs conducción.",
      solution: "Fichaje móvil geolocalizado al subir al furgón y reporte automático de jornada.",
      mrr: 47.50,
      emailSubject: "Registro de jornada para conductores de Trans-Utrera (evitar discrepancias horarias)",
      emailBody: `Hola Joaquín,

Te contacto porque con 19 repartidores en carretera, controlar el inicio y fin de jornada cuando los vehículos no pasan siempre por la base es motivo habitual de discrepancias laborales e inspecciones.

Nuestra aplicación permite que cada transportista fiche desde su propio teléfono móvil con geolocalización al arrancar y terminar ruta, registrando pausas reglamentarias con total transparencia y cumpliendo la normativa laboral.

• Control total sin dispositivos GPS costosos en cada vehículo.
• Justificación exacta de horas extraordinarias y dietas.
• Integración con la facturación y nóminas.

Coste: 2,50 €/chofer/mes.

¿Hacemos una demo de 10 minutos por teléfono o te dejo un usuario demo para que lo veas con un conductor?`,
      waBody: `Hola Joaquín, te escribo de Utrecar Soluciones. Con los repartidores en carretera suele ser difícil cuadrar los partes de horas que exige Inspección de Trabajo. Con nuestra app fichan desde el móvil al arrancar y parar ruta, con ubicación GPS y sin papeles. Son 2,50€/mes por conductor. ¿Te paso una demo de 2 minutos para ver la pantalla?`
    },

    asesoria: {
      name: "Gestoría & Asesoría Laboral Triana",
      sector: "Asesoría Laboral y Fiscal (180 pymes clientes)",
      employees: 14,
      location: "Sevilla (Triana)",
      contact: "Antonio Morales",
      role: "Socio Director / Graduado Social",
      email: "amorales@asesoriatriana.com",
      phone: "+34 954 27 55 11",
      pain: "Clientes que envían tarde los excels de horas para hacer las nóminas y clientes multados por inspección.",
      solution: "Portal de Asesoría: acceso centralizado para descargar informes de horas de todas sus pymes con 1 clic + comisión de partner.",
      mrr: 350.00,
      emailSubject: "Propuesta Partner Asesorías: automatizar el control horario de vuestras 180 pymes",
      emailBody: `Estimado Antonio,

Como graduado social y director de Asesoría Triana, seguro que a final de cada mes vivís el atasco de reclamar a vuestras pymes clientes los resúmenes de horas trabajadas para poder cerrar las nóminas a tiempo.

Queremos proponeros un acuerdo de Colaboración / Partner con Utrecar:
• Facilitamos a vuestras pymes clientes nuestra app de control horario legal (2,50€/empleado).
• Vuestro despacho cuenta con un **Panel de Asesoría gratuito** para descargar el resumen mensual de horas de todos vuestros clientes con 1 solo clic.
• Generáis un ingreso recurrente adicional como prescriptores recomendados.

¿Te parecería interesante que tengamos una breve llamada de 10 minutos esta semana para explicarte las condiciones para vuestro despacho?`,
      waBody: `Hola Antonio, te contacto de Utrecar. Hemos desarrollado un Portal de Asesoría para despachos laborales que permite a vuestros clientes pyme fichar por app/tablet y a vosotros descargar todas las horas para nóminas con 1 clic, ahorrándoos cientos de llamadas a final de mes. ¿Podemos ver una demo rápida esta semana?`
    }
  };

  let currentCompanyKey = 'clima';
  let currentChannel = 'email';
  let isScanning = false;

  // --- UI Elements ---
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const presetCards = document.querySelectorAll('.preset-card');

  const btnRunAgent = document.getElementById('btn-run-agent');
  const scanBox = document.getElementById('scan-box');
  const scanStatusText = document.getElementById('scan-status-text');
  const messageBody = document.getElementById('message-body-text');
  const messageContainer = document.getElementById('message-container');
  const emailMetaBlock = document.getElementById('email-meta-block');
  const emailToVal = document.getElementById('email-to-val');
  const emailSubjectVal = document.getElementById('email-subject-val');

  const btnChanEmail = document.getElementById('btn-chan-email');
  const btnChanWa = document.getElementById('btn-chan-wa');
  const btnCopyMsg = document.getElementById('btn-copy-msg');
  const btnSendSim = document.getElementById('btn-send-sim');
  const simAlert = document.getElementById('sim-alert');

  // Tab 2 Chat Elements
  const chatMessagesContainer = document.getElementById('chat-messages-container');
  const chatInput = document.getElementById('chat-input');
  const btnSendUserMsg = document.getElementById('btn-send-user-msg');
  const quickPillBtns = document.querySelectorAll('.pill-btn');
  const threadItems = document.querySelectorAll('.thread-item');
  const btnPushOdooChat = document.getElementById('btn-push-odoo-chat');

  // Tab 3 Odoo Elements
  const odooLeadName = document.getElementById('odoo-lead-name');
  const odooSheetTitle = document.getElementById('odoo-sheet-title');
  const odooMrrVal = document.getElementById('odoo-mrr-val');
  const odooArrVal = document.getElementById('odoo-arr-val');
  const odooFieldCompany = document.getElementById('odoo-field-company');
  const odooFieldContact = document.getElementById('odoo-field-contact');
  const odooFieldEmail = document.getElementById('odoo-field-email');
  const odooFieldPhone = document.getElementById('odoo-field-phone');
  const odooAiNotes = document.getElementById('odoo-ai-notes');
  const odooPayloadCode = document.getElementById('odoo-payload-code');

  // Tab 4 ROI Elements
  const sliderEmp = document.getElementById('slider-emp');
  const sliderHours = document.getElementById('slider-hours');
  const sliderWage = document.getElementById('slider-wage');
  const valEmpDisplay = document.getElementById('val-emp-display');
  const valHoursDisplay = document.getElementById('val-hours-display');
  const valWageDisplay = document.getElementById('val-wage-display');
  const roiAppCost = document.getElementById('roi-app-cost');
  const roiTimeSaving = document.getElementById('roi-time-saving');
  const roiNetBenefit = document.getElementById('roi-net-benefit');
  const roiReturnMult = document.getElementById('roi-return-mult');

  // --- Tab Navigation ---
  function switchTab(tabId) {
    navTabs.forEach(tab => {
      if (tab.getAttribute('data-tab') === tabId) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });

    tabPanes.forEach(pane => {
      if (pane.id === tabId) {
        pane.classList.add('active');
      } else {
        pane.classList.remove('active');
      }
    });
  }

  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabId = tab.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  // --- Company Presets ---
  presetCards.forEach(card => {
    card.addEventListener('click', () => {
      presetCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      currentCompanyKey = card.getAttribute('data-company');
      updateCompanyProfileUI();
      // Reset message view
      messageBody.textContent = `Empresa seleccionada: ${companyData[currentCompanyKey].name}.\nHaz clic en "Analizar con IA y Generar Propuesta" para activar el agente.`;
      simAlert.style.display = 'none';
    });
  });

  // Custom Company Apply
  document.getElementById('btn-apply-custom').addEventListener('click', () => {
    const cName = document.getElementById('custom-name').value || "Empresa Personalizada SL";
    const cSector = document.getElementById('custom-sector').value || "Servicios";
    const cEmp = parseInt(document.getElementById('custom-employees').value, 10) || 20;
    const cCity = document.getElementById('custom-city').value || "Sevilla";

    companyData.custom = {
      name: cName,
      sector: cSector,
      employees: cEmp,
      location: cCity,
      contact: "Responsable de Operaciones",
      role: "Gerente / Dirección",
      email: `contacto@${cName.toLowerCase().replace(/[^a-z0-9]/g, '')}.es`,
      phone: "+34 954 00 00 00",
      pain: `Gestión de ${cEmp} empleados y cumplimiento normativo de registro de jornada sin papel.`,
      solution: "Control digital por app móvil o tablet con geolocalización y panel cloud.",
      mrr: (cEmp * 2.5).toFixed(2),
      emailSubject: `Control horario y gestión de plantilla en ${cName} (cumplimiento ITSS)`,
      emailBody: `Hola,

Te contacto porque en ${cName} contáis con un equipo de aproximadamente ${cEmp} personas en ${cCity}.

Con la intensificación de las inspecciones laborales sobre el registro digital de jornada y control de turnos, muchas empresas del sector ${cSector} buscan eliminar las hojas de papel y los excels.

En Utrecar ofrecemos una app de fichaje en 2 segundos con geolocalización o tablet quiosco por 2,50€/mes por empleado.

¿Te parecería bien que te active 14 días de prueba gratuita sin compromiso?`,
      waBody: `Hola, te escribo de Utrecar. Para ${cName} tenemos una solución de control horario donde vuestros ${cEmp} empleados fichan por móvil o tablet con total validez legal ante inspección. Cuesta 2,50€/mes por empleado. ¿Quieres probarlo 14 días gratis?`
    };

    currentCompanyKey = 'custom';
    presetCards.forEach(c => c.classList.remove('active'));
    updateCompanyProfileUI();
    messageBody.textContent = `Empresa personalizada cargada: ${cName}.\nHaz clic en "Analizar con IA y Generar Propuesta".`;
  });

  function updateCompanyProfileUI() {
    const data = companyData[currentCompanyKey];
    document.getElementById('prof-company').textContent = data.name;
    document.getElementById('prof-decisor').innerHTML = `<strong>Decisor detectado:</strong> ${data.contact} • ${data.role}`;
    document.getElementById('prof-chip-sector').textContent = `Sector: ${data.sector}`;
    document.getElementById('prof-chip-emp').textContent = `Plantilla: ~${data.employees} operarios`;

    // Email meta
    emailToVal.textContent = `${data.email} (${data.contact})`;
    emailSubjectVal.textContent = data.emailSubject;

    // Synchronize Odoo Sheet
    updateOdooSheet(data);
  }

  function updateOdooSheet(data) {
    odooLeadName.textContent = `Control Horario - ${data.name} (${data.employees} Empleados)`;
    odooSheetTitle.textContent = `Control Horario & Turnos - ${data.name}`;
    odooMrrVal.textContent = `${parseFloat(data.mrr).toFixed(2)} € / mes`;
    odooArrVal.textContent = `${(parseFloat(data.mrr) * 12).toFixed(2)} € / año`;
    odooFieldCompany.textContent = data.name;
    odooFieldContact.textContent = `${data.contact} (${data.role})`;
    odooFieldEmail.textContent = data.email;
    odooFieldPhone.textContent = data.phone;

    odooAiNotes.innerHTML = `
      <p><strong>• Situación detectada:</strong> ${data.sector} con aprox. ${data.employees} empleados en ${data.location}.</p>
      <p><strong>• Dolor identificado:</strong> ${data.pain}</p>
      <p><strong>• Solución y oferta:</strong> ${data.solution} Licencia SaaS estimada en ${parseFloat(data.mrr).toFixed(2)}€/mes (2,50€/u). Demostración o prueba de 14 días propuesta.</p>
    `;

    odooPayloadCode.textContent = JSON.stringify({
      model: "crm.lead",
      method: "create",
      args: [{
        name: `Control Horario - ${data.name} (${data.employees} Empleados)`,
        partner_name: data.name,
        contact_name: data.contact,
        email_from: data.email,
        phone: data.phone,
        expected_revenue: parseFloat(data.mrr) * 12,
        recurring_revenue_monthly: parseFloat(data.mrr),
        probability: 85,
        stage_id: 3,
        tag_ids: [12, 18],
        description: `Lead generado automáticamente por el Agente Comercial IA Utrecar para ${data.name}. Dolor: ${data.pain}`
      }]
    }, null, 2);
  }

  // --- Typewriter Effect ---
  function typeWriter(text, element, speed = 12) {
    element.textContent = '';
    let i = 0;
    function type() {
      if (i < text.length) {
        element.textContent += text.charAt(i);
        i++;
        setTimeout(type, speed);
      }
    }
    type();
  }

  // --- Run Agent Scan & Generation ---
  btnRunAgent.addEventListener('click', () => {
    if (isScanning) return;
    isScanning = true;
    scanBox.style.display = 'block';
    simAlert.style.display = 'none';

    const steps = [
      { id: 'scan-step-1', text: "1. Extrayendo datos web corporativa y actividad comercial..." },
      { id: 'scan-step-2', text: "2. Identificando decisores clave (Operaciones / RRHH / Gerencia)..." },
      { id: 'scan-step-3', text: "3. Calculando riesgos normativos (RD-ley 8/2019 / LISOS / Fichajes)..." },
      { id: 'scan-step-4', text: "4. Construyendo propuesta de valor personalizada de Utrecar..." }
    ];

    steps.forEach((s, idx) => {
      const el = document.getElementById(s.id);
      el.classList.remove('completed', 'active');
      setTimeout(() => {
        el.classList.add('active');
        scanStatusText.textContent = s.text;
      }, idx * 600);
      setTimeout(() => {
        el.classList.remove('active');
        el.classList.add('completed');
      }, (idx + 1) * 600);
    });

    setTimeout(() => {
      isScanning = false;
      scanStatusText.textContent = "✅ Análisis finalizado. Mensaje generado por el LLM:";
      
      const data = companyData[currentCompanyKey];
      const targetText = (currentChannel === 'email') ? data.emailBody : data.waBody;
      typeWriter(targetText, messageBody, 10);
    }, 2600);
  });

  // --- Channel Switcher (Email vs WhatsApp) ---
  btnChanEmail.addEventListener('click', () => {
    currentChannel = 'email';
    btnChanEmail.classList.add('active');
    btnChanWa.classList.remove('active');
    messageContainer.classList.remove('wa-mode');
    messageContainer.classList.add('email-mode');
    emailMetaBlock.style.display = 'flex';

    const data = companyData[currentCompanyKey];
    messageBody.textContent = data.emailBody;
  });

  btnChanWa.addEventListener('click', () => {
    currentChannel = 'whatsapp';
    btnChanWa.classList.add('active');
    btnChanEmail.classList.remove('active');
    messageContainer.classList.remove('email-mode');
    messageContainer.classList.add('wa-mode');
    emailMetaBlock.style.display = 'none';

    const data = companyData[currentCompanyKey];
    messageBody.textContent = data.waBody;
  });

  // --- Copy Text ---
  btnCopyMsg.addEventListener('click', () => {
    navigator.clipboard.writeText(messageBody.textContent).then(() => {
      const originalText = btnCopyMsg.innerHTML;
      btnCopyMsg.innerHTML = "<span>✅ ¡Copiado!</span>";
      setTimeout(() => { btnCopyMsg.innerHTML = originalText; }, 2000);
    });
  });

  // --- Simulate Send ---
  btnSendSim.addEventListener('click', () => {
    simAlert.style.display = 'block';
    // Update KPI
    const sentEl = document.getElementById('kpi-sent');
    sentEl.textContent = parseInt(sentEl.textContent, 10) + 1;

    // Increment badge
    const badge = document.getElementById('inbox-badge');
    badge.textContent = "NUEVO";
    badge.style.background = "#10b981";
    badge.style.color = "#ffffff";
  });

  // --- Tab 2: Chat & Objection Simulator ---
  const objectionResponses = {
    legal: `Por supuesto. Nuestro software cumple al 100% con el **Real Decreto-ley 8/2019** y los requisitos más recientes de la **Inspección de Trabajo (ITSS)**:
• Registro diario fehaciente de hora de inicio, pausas y fin.
• Totalmente inalterable y con trazabilidad digital certificada (sin posibilidad de falsear a posteriori como en el papel).
• Conservación automática durante los 4 años legales obligatorios en la nube.
• Exportación inmediata en PDF o Excel en formato oficial ante cualquier visita de un inspector de trabajo.`,

    vacaciones: `Es uno de los módulos favoritos de nuestros clientes:
• Los empleados solicitan vacaciones, permisos o justificantes médicos directamente desde su app móvil con 2 toques.
• Los supervisores reciben la notificación y aprueban o rechazan con 1 clic.
• El calendario de cuadrantes se actualiza automáticamente en tiempo real para evitar que dos técnicos o camareros clave coincidan en el mismo día sin cubrir el turno.`,

    gestoria: `¡Totalmente! Está diseñado precisamente para ahorraros esa fricción a final de mes:
• Permite exportar resúmenes consolidados de horas ordinarias, horas extraordinarias y festivos trabajados por trabajador.
• Es 100% compatible con los principales programas de nóminas (A3, Sage, Wolters Kluwer) y con **Odoo ERP**.
• Además, si lo deseáis, podéis darle un acceso gratuito directo de solo lectura a vuestro graduado social para que se descargue los datos sin tener que pedíroslos.`,

    demo: `¡Perfecto Manuel! Ya he reservado el hueco para mañana a las **11:30h**.

Te he enviado la invitación de videollamada a tu correo (**manuel.rivas@climagualdaquivir.es**) con el enlace de Google Meet. 

Además, he creado automáticamente la ficha de vuestra empresa en nuestro sistema **Odoo 17 CRM** para asignarte a nuestro técnico especialista y que tengáis listo un entorno de prueba de 14 días. ¡Hablamos mañana!`
  };

  function addChatMessage(author, text, isAi = false) {
    const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${isAi ? 'ai-msg' : 'prospect-msg'}`;
    
    msgDiv.innerHTML = `
      <div class="msg-bubble">
        <div class="msg-author">${author}</div>
        <p>${text.replace(/\n/g, '<br>')}</p>
        <span class="msg-time">${timeNow} ${isAi ? '• <em>Respuesta automática IA</em>' : ''}</span>
      </div>
    `;
    
    chatMessagesContainer.appendChild(msgDiv);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
  }

  function handleUserQuery(queryText, pillType = null) {
    if (!queryText.trim()) return;

    // Add user message
    addChatMessage("Manuel Rivas (Cliente)", queryText, false);
    chatInput.value = '';

    // Show typing state then reply
    setTimeout(() => {
      let reply = "";
      if (pillType && objectionResponses[pillType]) {
        reply = objectionResponses[pillType];
        if (pillType === 'demo') {
          // Update Odoo
          document.getElementById('odoo-field-nextact').textContent = "📅 Videollamada Demo (Mañana 11:30h)";
          document.getElementById('kpi-demos').textContent = parseInt(document.getElementById('kpi-demos').textContent, 10) + 1;
        }
      } else {
        // Generic AI Sales response for free text
        reply = `Entiendo perfectamente tu consulta sobre "${queryText}". Nuestro sistema de control horario Utrecar está diseñado justo para dar respuesta flexible a ese escenario sin añadir fricción a los trabajadores ni a administración. ¿Te gustaría que lo veamos en vivo sobre la pantalla en una llamada rápida de 5 minutos o prefieres probarlo directamente en tu móvil con una clave de acceso?`;
      }

      addChatMessage("Agente IA Utrecar (Comercial)", reply, true);
    }, 700);
  }

  btnSendUserMsg.addEventListener('click', () => {
    handleUserQuery(chatInput.value);
  });

  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      handleUserQuery(chatInput.value);
    }
  });

  quickPillBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const qType = btn.getAttribute('data-query');
      const text = btn.textContent.replace(/^[^"]*"|"[^"]*$/g, '');
      handleUserQuery(text, qType);
    });
  });

  btnPushOdooChat.addEventListener('click', () => {
    switchTab('tab-odoo');
  });

  // Thread switcher
  threadItems.forEach(item => {
    item.addEventListener('click', () => {
      threadItems.forEach(t => t.classList.remove('active'));
      item.classList.add('active');
      const threadKey = item.getAttribute('data-thread');
      if (companyData[threadKey]) {
        currentCompanyKey = threadKey;
        updateCompanyProfileUI();
        document.getElementById('chat-title').textContent = `${companyData[threadKey].contact} • ${companyData[threadKey].role}`;
        document.getElementById('chat-subtitle').textContent = `${companyData[threadKey].name} • ${companyData[threadKey].employees} empleados`;
      }
    });
  });

  // --- TAB 4: ROI CALCULATOR ---
  function recalculateROI() {
    const emp = parseInt(sliderEmp.value, 10);
    const hours = parseInt(sliderHours.value, 10);
    const wage = parseInt(sliderWage.value, 10);

    valEmpDisplay.textContent = emp;
    valHoursDisplay.textContent = `${hours} h`;
    valWageDisplay.textContent = `${wage} €/h`;

    const appCostMonth = emp * 2.50;
    const timeSavingMonth = hours * wage;
    const netBenefitYear = (timeSavingMonth - appCostMonth) * 12;
    const roiMultiplier = Math.round(((timeSavingMonth * 12) / (appCostMonth * 12)) * 100);

    roiAppCost.textContent = `${appCostMonth.toFixed(0)} € / mes`;
    roiTimeSaving.textContent = `${timeSavingMonth.toFixed(0)} € / mes`;
    roiNetBenefit.textContent = `+${netBenefitYear.toLocaleString('es-ES')} €`;
    roiReturnMult.textContent = `Retorno de inversión: ${roiMultiplier}%`;
  }

  sliderEmp.addEventListener('input', recalculateROI);
  sliderHours.addEventListener('input', recalculateROI);
  sliderWage.addEventListener('input', recalculateROI);

  // Initialize
  updateCompanyProfileUI();
  recalculateROI();
});
