from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.constants import APP_NAME, APP_VERSION


_GUIDE_HTML = f"""\
<h1 style="color:#58a6ff;">{APP_NAME} v{APP_VERSION}</h1>
<p style="color:#bbbbbb; font-size:14px;">
    Gestione completa di Docker, servizi di sistema e macchine virtuali &mdash;
    in locale o via SSH.
</p>

<hr style="border: 1px solid #333333;">

<h2 style="color:#e0e0e0;">SERVER</h2>

<h3 style="color:#58a6ff;">Dashboard</h3>
<p>Informazioni di sistema in tempo reale: hostname, kernel, OS, CPU, RAM,
disco, porte aperte e indirizzi IP delle interfacce di rete.
Metriche aggiornate automaticamente ogni 5 secondi.</p>

<h3 style="color:#58a6ff;">Terminal</h3>
<p>Terminale interattivo integrato. Supporta piu' tab contemporanei.
Funziona sia in locale che su server remoti via SSH.</p>

<h3 style="color:#58a6ff;">Processes</h3>
<p>Lista dei processi in esecuzione con PID, utente, CPU%, MEM%, comando.
Aggiornamento automatico. Possibilita' di terminare i processi.</p>

<h3 style="color:#58a6ff;">Applications</h3>
<p>Lista delle applicazioni installate (pacchetti .desktop).
Permette di cercare e filtrare le applicazioni.</p>

<h3 style="color:#58a6ff;">File Transfer</h3>
<p>Trasferimento file tra locale e remoto via SFTP.
Navigazione a doppio pannello, upload e download.</p>

<hr style="border: 1px solid #333333;">

<h2 style="color:#e0e0e0;">SYSTEM</h2>

<h3 style="color:#58a6ff;">Services</h3>
<p>Gestione servizi systemd: start, stop, restart, enable/disable al boot.
Filtro per nome e stato. Visualizzazione stato attivo e stato di boot.</p>

<h3 style="color:#58a6ff;">Packages</h3>
<p>Gestione pacchetti APT: lista pacchetti installati, ricerca,
installazione e rimozione pacchetti. Richiede sudo.</p>

<h3 style="color:#58a6ff;">Hosts File</h3>
<p>Editor del file <code>/etc/hosts</code>. Aggiunta, modifica e rimozione
di mapping hostname &rarr; IP. Richiede sudo.</p>

<h3 style="color:#58a6ff;">Network</h3>
<p>Configurazione connessioni di rete tramite NetworkManager.
Visualizzazione interfacce, indirizzi MAC e IP.</p>

<h3 style="color:#58a6ff;">Firewall</h3>
<p>Gestione regole UFW (Uncomplicated Firewall).
Aggiunta e rimozione regole, abilitazione/disabilitazione firewall.
Richiede sudo.</p>

<h3 style="color:#58a6ff;">Net Tools</h3>
<p>Strumenti di rete: ping, traceroute, nslookup, port scan (netcat).
Esecuzione comandi con output in tempo reale.</p>

<h3 style="color:#58a6ff;">APT Repos</h3>
<p>Gestione repository APT: lista sorgenti configurate,
aggiunta e rimozione repository. Richiede sudo.</p>

<h3 style="color:#58a6ff;">Startup</h3>
<p>Gestione applicazioni all'avvio: lista, abilitazione e disabilitazione
dei programmi che si avviano con il sistema.</p>

<h3 style="color:#58a6ff;">System Logs</h3>
<p>Visualizzazione log di sistema tramite <code>journalctl</code>.
Filtri per unit, priorita', periodo temporale e numero di righe.
Filtro keyword in tempo reale.</p>

<h3 style="color:#58a6ff;">Cron Jobs</h3>
<p>Gestione cron job: visualizzazione, aggiunta, rimozione e toggle
(abilita/disabilita) dei job pianificati. Supporta utente corrente e root.
Presets per schedule comuni (ogni minuto, ora, giorno, settimana, mese, reboot).</p>

<h3 style="color:#58a6ff;">Users &amp; Groups</h3>
<p>Gestione utenti e gruppi di sistema. Tab Users: lista utenti con UID, GID,
home, shell. Aggiunta e rimozione utenti (richiede sudo).
Tab Groups: visualizzazione gruppi con membri.</p>

<h3 style="color:#58a6ff;">Disk Usage</h3>
<p>Visualizzazione utilizzo disco con card grafiche per ogni filesystem.
Barre di progresso colorate (verde &lt; 70%, giallo &lt; 90%, rosso &ge; 90%).
Dimensione totale, usata e libera per ogni partizione.</p>

<hr style="border: 1px solid #333333;">

<h2 style="color:#e0e0e0;">DOCKER</h2>

<h3 style="color:#58a6ff;">Containers</h3>
<p>Gestione container Docker: lista con stato, start, stop, kill, restart,
remove. Visualizzazione log con filtro keyword e auto-scroll.
Statistiche in tempo reale. Exec shell interattiva nel container.
Menu contestuale con tutte le azioni.</p>

<h3 style="color:#58a6ff;">Images</h3>
<p>Gestione immagini Docker: lista, pull, build da Dockerfile, remove.
Visualizzazione dimensione, tag e data di creazione.
Build dialog con output streaming in tempo reale.</p>

<h3 style="color:#58a6ff;">Volumes</h3>
<p>Gestione volumi Docker: lista, creazione, rimozione, inspect.
Visualizzazione driver, mountpoint e dimensione.</p>

<h3 style="color:#58a6ff;">Networks</h3>
<p>Gestione reti Docker: lista, creazione, rimozione, inspect.
Visualizzazione driver, subnet e container connessi.</p>

<h3 style="color:#58a6ff;">Compose</h3>
<p>Gestione progetti Docker Compose: lista progetti,
up, down, restart, logs dei servizi.</p>

<h3 style="color:#58a6ff;">Registry</h3>
<p>Ricerca immagini su Docker Hub. Risultati con nome, descrizione,
stelle, stato official/automated. Pull diretto dell'immagine selezionata
con scelta del tag.</p>

<hr style="border: 1px solid #333333;">

<h2 style="color:#e0e0e0;">VIRTUALIZATION</h2>

<h3 style="color:#58a6ff;">Virtual Machines</h3>
<p>Gestione VM libvirt/KVM/QEMU tramite <code>virsh</code>:</p>
<ul>
    <li><b>Lifecycle</b>: Start, Shutdown, Force Off, Reboot, Suspend, Resume</li>
    <li><b>Autostart</b>: Abilita/disabilita avvio automatico</li>
    <li><b>Delete</b>: Elimina definizione VM (con conferma)</li>
    <li><b>Dettagli</b>: Dischi, interfacce di rete, indirizzi IP, statistiche memoria</li>
    <li><b>Snapshot</b>: Crea, ripristina, elimina snapshot</li>
    <li><b>Export/Import</b>: Esporta XML e dischi, importa da file XML</li>
    <li><b>Clone</b>: Clona VM con <code>virt-clone</code></li>
    <li><b>Import as Server</b>: Importa una VM come server SSH nella sidebar</li>
</ul>

<hr style="border: 1px solid #333333;">

<h2 style="color:#e0e0e0;">CONNESSIONI</h2>

<h3 style="color:#58a6ff;">Server remoti</h3>
<p>Nella sidebar, sezione SERVERS: aggiungi, modifica o elimina server remoti.
Supporta autenticazione con chiave SSH o password.
La connessione avviene via SSH tunnel per Docker e comandi di sistema.</p>

<h3 style="color:#58a6ff;">Sudo</h3>
<p>La password sudo viene richiesta automaticamente quando serve
per un'operazione amministrativa (pacchetti, hosts, firewall, servizi, ecc.).
Non viene mai salvata su disco &mdash; solo in memoria per la sessione corrente.
Puoi impostarla o cambiarla manualmente cliccando sull'icona lucchetto
nella barra di stato.</p>

<hr style="border: 1px solid #333333;">

<h2 style="color:#e0e0e0;">IMPOSTAZIONI</h2>
<p>Accessibili dal pulsante <b>Settings</b> in fondo alla sidebar.
Configurazione font del terminale, intervalli di polling,
gestione server (import/export), preferenze varie.</p>
"""


class GuideView(QWidget):
    """Read-only guide page listing all application features."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 24, 32, 24)

        label = QLabel(_GUIDE_HTML)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet("color: #cccccc; font-size: 13px; line-height: 1.5;")
        label.setOpenExternalLinks(True)
        content_layout.addWidget(label)
        content_layout.addStretch()

        scroll.setWidget(content)
