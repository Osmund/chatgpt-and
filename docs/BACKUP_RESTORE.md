# Database Backup & Restore

## 📦 Backup

### Ta backup
```bash
./scripts/backup_database.sh
```

**Hva backupes:**
- `duck_memory.db` - Hoveddatabase (minner, facts, meldinger)
- `chatgpt_voice.db` - Samtalelogg
- `*-embedding.bin` - Embedding cache-filer
- Session state filer (hvis de finnes)

**Backup plassering:** `/home/admog/Code/chatgpt-and/backups/`

**Format:** `duck_backup_YYYYMMDD_HHMMSS.tar.gz`

### Automatisk backup før kritiske endringer

Før du gjør strukturelle endringer (som multi-user migration):
```bash
# Ta navngitt backup
./scripts/backup_database.sh
# Backupen får automatisk timestamp
```

## ♻️ Restore

### Liste tilgjengelige backups
```bash
ls -lht backups/*.tar.gz
```

### Restore fra backup
```bash
./scripts/restore_database.sh duck_backup_20260113_140808.tar.gz
```

eller bare filnavnet:
```bash
./scripts/restore_database.sh duck_backup_20260113_140808.tar.gz
```

**Restore prosess:**
1. Stopper ChatGPT Duck tjenester
2. Tar sikkerhetskopi av nåværende database (pre_restore_*)
3. Pakker ut og kopierer backup-filer
4. Spør om å starte tjenester igjen

### Safety net
Ved restore blir nåværende database automatisk backupet til:
```
backups/pre_restore_YYYYMMDD_HHMMSS.tar.gz
```

Dette gir deg mulighet til å gå tilbake hvis restore ikke fungerte som forventet.

## 🔄 Rutine

### Før migration (anbefalt)
```bash
# 1. Ta backup
./scripts/backup_database.sh

# 2. Kjør migration
python3 scripts/migrate_multi_user.py

# 3. Test systemet
# Hvis noe går galt:
./scripts/restore_database.sh <backup_fil>
```

### Daglig backup (optional)
Legg til i crontab for automatisk backup hver dag kl 03:00:
```bash
crontab -e
```

Legg til:
```
0 3 * * * /home/admog/Code/chatgpt-and/scripts/backup_database.sh >> /tmp/duck_backup.log 2>&1
```

### Cleanup gamle backups
Backups eldre enn 30 dager slettes IKKE automatisk.

Manuell cleanup:
```bash
# Vis backups eldre enn 30 dager
find backups/ -name "duck_backup_*.tar.gz" -mtime +30

# Slett (vær forsiktig!)
find backups/ -name "duck_backup_*.tar.gz" -mtime +30 -delete
```

## 📊 Backup info

Hver backup inneholder en `backup_info.txt` fil med:
- Timestamp
- Database statistikk (antall meldinger, minner, facts)
- Filliste

Vis backup info uten å restore:
```bash
tar -xzOf backups/duck_backup_20260113_140808.tar.gz */backup_info.txt
```

## 🚨 Emergency Restore

Hvis systemet er helt ødelagt:

1. **Stopp tjenester:**
   ```bash
   sudo systemctl stop chatgpt-duck duck-control
   ```

2. **Restore siste backup:**
   ```bash
   cd /home/admog/Code/chatgpt-and
   ./scripts/restore_database.sh backups/duck_backup_<siste>.tar.gz
   ```

3. **Start tjenester:**
   ```bash
   sudo systemctl start chatgpt-duck duck-control
   ```

4. **Verifiser:**
   ```bash
   sudo systemctl status chatgpt-duck
   curl http://localhost:3000/api/memory/stats
   ```

## 🧪 Test Restore (anbefalt før production)

Test restore-prosessen i en sikker miljø:

```bash
# 1. Ta backup
./scripts/backup_database.sh

# 2. Gjør en test-endring
sqlite3 duck_memory.db "INSERT INTO memories (text, topic, first_seen, last_accessed) VALUES ('TEST', 'test', datetime('now'), datetime('now'))"

# 3. Restore
./scripts/restore_database.sh <backup_fil>

# 4. Verifiser at TEST er borte
sqlite3 duck_memory.db "SELECT * FROM memories WHERE topic='test'"
```

## 💡 Tips

- **Før store endringer:** Alltid ta backup først
- **Test restore:** Verifiser at restore fungerer før du trenger det
- **Oppbevar viktige backups:** Kopier kritiske backups til annen disk/sky
- **Dokumenter endringer:** Legg ved notater i backup-mappa om hva som ble endret

## 📝 Backup størrelse

Typisk størrelse (komprimert):
- Minimal database: ~10-50 KB
- Etter 1 uke bruk: ~500 KB - 1 MB
- Etter 1 måned: ~2-5 MB
- Med mange embeddings: +100-500 KB

Komprimeringen reduserer størrelse med ~60-80%.
