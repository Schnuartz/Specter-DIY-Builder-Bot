# Specter DIY Builder Bot

Ein Telegram-Bot für die Specter DIY Builder Community, der automatisch Erinnerungen für den wöchentlichen Call sendet und nach dem Call Links zur YouTube-Aufzeichnung postet.

## Features

- **Automatische Erinnerungen** für den wöchentlichen Call (Donnerstag 17:00 CET)
  - 3 Tage vorher (Montag)
  - 1 Tag vorher (Mittwoch)
  - 1 Stunde vorher (Donnerstag)
- **Automatisches Posten** der YouTube-Aufzeichnung nach dem Call
- **Zusammenfassung** aus der Video-Beschreibung extrahiert
- **Bot-Befehle** für manuelle Interaktion

## Bot-Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `/start` | Zeigt Willkommensnachricht |
| `/status` | Zeigt Bot-Status |
| `/nextcall` | Zeigt nächsten Call-Termin |
| `/latestvideo` | Zeigt das neueste Video aus der Playlist |
| `/chatid` | Zeigt die Chat-ID (für Setup) |
| `/postvideo` | Manuell das neueste Video posten |

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/FinnFrei662/Specter-DIY-Builder-Bot.git
cd Specter-DIY-Builder-Bot
```

### 2. Python-Umgebung einrichten

```bash
# Virtuelle Umgebung erstellen
python -m venv venv

# Aktivieren (Windows)
venv\Scripts\activate

# Aktivieren (Linux/Mac)
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt
```

### 3. Konfiguration

1. Kopiere `.env.example` zu `.env`:
   ```bash
   cp .env.example .env
   ```

2. Bearbeite `.env` mit deinen Werten:
   ```
   TELEGRAM_BOT_TOKEN=dein_bot_token
   TELEGRAM_CHAT_ID=deine_chat_id
   ```

### 4. Chat-ID herausfinden

1. Füge den Bot zur Telegram-Gruppe hinzu
2. Sende `/chatid` in der Gruppe
3. Kopiere die angezeigte ID in deine `.env`

### 5. Bot starten

```bash
python bot.py
```

## Deployment

### Option A: Lokaler Server / Raspberry Pi

```bash
# Mit nohup im Hintergrund laufen lassen
nohup python bot.py > bot.log 2>&1 &

# Oder mit screen
screen -S specterbot
python bot.py
# Ctrl+A, D zum Detachen
```

### Option B: Systemd Service (Linux)

Erstelle `/etc/systemd/system/specterbot.service`:

```ini
[Unit]
Description=Specter DIY Builder Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Specter-DIY-Builder-Bot
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable specterbot
sudo systemctl start specterbot
```

### Option C: Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

## Konfiguration anpassen

### Zeitplan ändern

In `config.py` kannst du folgende Werte anpassen:

```python
CALL_DAY = "thursday"  # Tag des Calls
CALL_HOUR = 17         # Uhrzeit (24h Format)
TIMEZONE = "Europe/Berlin"
```

### Nachrichten anpassen

Die Nachrichten-Templates findest du ebenfalls in `config.py`:
- `REMINDER_MESSAGE_3_DAYS`
- `REMINDER_MESSAGE_1_DAY`
- `REMINDER_MESSAGE_1_HOUR`
- `POST_CALL_MESSAGE_TEMPLATE`

## Projektstruktur

```
Specter-DIY-Builder-Bot/
├── bot.py              # Hauptbot mit Scheduler
├── config.py           # Konfiguration und Messages
├── youtube_utils.py    # YouTube API Integration
├── requirements.txt    # Python Dependencies
├── .env.example        # Beispiel-Konfiguration
├── .gitignore          # Git Ignore Rules
└── README.md           # Diese Datei
```

## Troubleshooting

### Bot antwortet nicht
- Prüfe ob der Bot-Token korrekt ist
- Stelle sicher, dass der Bot zur Gruppe hinzugefügt wurde
- Überprüfe die Logs: `tail -f bot.log`

### Erinnerungen werden nicht gesendet
- Prüfe ob die `TELEGRAM_CHAT_ID` korrekt ist
- Stelle sicher, dass der Bot Admin-Rechte in der Gruppe hat (oder zumindest Nachrichten senden darf)

### YouTube-Videos werden nicht gefunden
- Überprüfe die `YOUTUBE_PLAYLIST_ID` in der `.env`
- Teste mit `python youtube_utils.py`

## Lizenz

MIT License

## Kontakt

Specter DIY Builder Community - [Telegram Gruppe](https://t.me/+93YQ5guL95syMmYy)
