# Security Audit: Hardcoded Sensitive Information

## Files with Hardcoded Personal Data

### 🔴 HIGH PRIORITY - Remove from version control

#### 1. `add_contacts.py` (Lines 15, 26)
- Contains real phone numbers
- **Action:** Delete file or move to .gitignore
- **Reason:** One-time setup script with personal data

#### 2. `send_apology_to_vikram.py` (Line 16)
- Contains specific contact phone number
- **Action:** Delete file (was one-time use)

#### 3. `send_intro_kolbjorn_rune.py` (Lines 23-24)
- Contains two phone numbers
- **Action:** Delete file (was one-time use)

#### 4. `test_twilio_sms.py` (Line 11)
- Contains Twilio FROM_NUMBER
- **Action:** Change to `os.getenv('TWILIO_PHONE_NUMBER')`

### 🟡 MEDIUM PRIORITY - Generic references OK

#### 5. `chatgpt_voice.py`
- References to "primary user" hardcoded as specific name
- Lines: 483, 485-486, 488-489, 590, 592-595, 598
- **Action:** Use `primary_user['username']` instead of hardcoded name
- **Current:** `'Osmund'` hardcoded
- **Should be:** `primary_user['username']` from user_manager

#### 6. `src/duck_ai.py`
- References to primary user in perspective context
- Lines: 422-423, 428-429, 434, 563
- **Action:** Use variable instead of hardcoded name
- **Reason:** Makes code reusable for other users

#### 7. `src/duck_sms.py`
- Fallback message mentions primary user name (Line 435, 791)
- Test data with phone number (Line 812)
- **Action:** 
  - Use variable for user name in messages
  - Remove or anonymize test phone number

### 🟢 LOW PRIORITY - Acceptable

#### 8. `sms-relay/app.py` (Line 96)
- Example IP address (192.168.1.50) in comment
- **Action:** None needed (example only)

#### 9. Domain references (duckberry.no)
- Lines in chatgpt_voice.py: 56, 89
- **Action:** Already using `os.getenv('SMS_RELAY_URL')`
- **Status:** ✅ Correct - fallback is fine

---

## Recommended Actions

### Immediate (Before Git Commit)

1. **Delete one-time scripts:**
```bash
rm send_apology_to_vikram.py
rm send_intro_kolbjorn_rune.py
rm add_contacts.py
```

2. **Update .gitignore:**
```gitignore
# One-time setup scripts with personal data
add_contacts.py
send_intro_*.py
send_apology_*.py
test_awareness.py

# Temporary test files
test_twilio_sms.py
```

3. **Fix test_twilio_sms.py:**
```python
# Line 11 - Change:
FROM_NUMBER = '+19784941666'
# To:
FROM_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
```

### Medium-term (Code Quality)

4. **Replace hardcoded user references in chatgpt_voice.py:**
```python
# Instead of:
user_manager.switch_user('Osmund', 'Osmund', 'owner')
speak("Hei Osmund, jeg har byttet tilbake til deg etter timeout.", ...)

# Use:
primary_user = user_manager.get_primary_user()
user_manager.switch_user(primary_user['username'], primary_user['display_name'], 'owner')
speak(f"Hei {primary_user['display_name']}, jeg har byttet tilbake til deg etter timeout.", ...)
```

5. **Update duck_ai.py perspective context:**
```python
# Instead of:
f"- Fakta om familie er Osmunds familie"

# Use:
f"- Fakta om familie er {primary_user['username']}s familie"
```

6. **Update duck_sms.py fallback messages:**
```python
# Instead of:
f"Lurer på hva du holder på med? Osmund er ikke hjemme 🦆"

# Use:
primary_user = user_manager.get_primary_user() if user_manager else {'username': 'owner'}
f"Lurer på hva du holder på med? {primary_user['username']} er ikke hjemme 🦆"
```

---

## Database Considerations

### Current State
The SQLite database (`duck_memory.db`) contains:
- Real phone numbers in `sms_contacts` table
- SMS message history in `sms_history` table
- Personal facts in `profile_facts` table

### Recommendations
1. **Add to .gitignore:**
```gitignore
duck_memory.db
duck_memory.db-journal
*.db
*.db-journal
```

2. **Create anonymized test database:**
```bash
# Create template with structure only
sqlite3 duck_memory_template.db < schema.sql
```

3. **Document data export for GDPR:**
```python
# Create script: export_user_data.py
# Exports all user data to JSON for compliance
```

---

## Summary

### Files to Delete
- ✅ `send_apology_to_vikram.py`
- ✅ `send_intro_kolbjorn_rune.py`  
- ✅ `add_contacts.py`

### Files to Update
- ⚠️ `test_twilio_sms.py` - Use env var
- ⚠️ `chatgpt_voice.py` - Replace hardcoded user references
- ⚠️ `src/duck_ai.py` - Use variables for user names
- ⚠️ `src/duck_sms.py` - Dynamic user references

### .gitignore Additions
```gitignore
# Database with personal data
duck_memory.db
duck_memory.db-journal
*.db
*.db-journal

# One-time scripts with personal info
add_contacts.py
send_intro_*.py
send_apology_*.py
test_awareness.py
test_twilio_sms.py

# Environment with secrets
.env
```

### Safe to Commit (Already Correct)
- ✅ `sms-relay/app.py` - Uses env vars
- ✅ Domain references - Use env vars with fallbacks
- ✅ Core SMS system - Generic implementation

---

## Prevention Checklist

Before committing:
- [ ] Check `git status` for .db files
- [ ] Review diffs for phone numbers (+47/+1)
- [ ] Search for hardcoded names: `grep -r "specific_name" --exclude-dir=.git`
- [ ] Verify .env not staged: `git status | grep .env`
- [ ] Test with anonymized database
- [ ] Review any test scripts for personal data

---

**Last Updated:** January 24, 2026
