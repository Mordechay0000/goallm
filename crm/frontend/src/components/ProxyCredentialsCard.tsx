/**
 * Personal proxy credentials: identity by username + password instead of by IP address.
 * Works when several families share one public IP (cellular / CGNAT), and needs no "bind device" step.
 * The password is shown only once, right after it is created.
 */
import React, { useEffect, useState } from 'react';
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import { bindingsApi, type ProxyCredentials } from '../api/bindings';

const Row: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <Stack direction="row" spacing={1} alignItems="center">
    <Typography variant="body2" color="text.secondary" sx={{ minWidth: 110 }}>
      {label}
    </Typography>
    <Typography component="code" sx={{ fontFamily: 'monospace', direction: 'ltr' }}>
      {value}
    </Typography>
    <Button size="small" onClick={() => navigator.clipboard?.writeText(value)}>
      העתק
    </Button>
  </Stack>
);

const ProxyCredentialsCard: React.FC = () => {
  const [creds, setCreds] = useState<ProxyCredentials | null>(null);
  const [newPassword, setNewPassword] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    bindingsApi.getProxyCredentials().then(setCreds).catch(() => setError('לא הצלחנו לטעון את פרטי ההתחברות'));
  }, []);

  const rotate = async () => {
    if (creds?.has_password && !window.confirm('ליצור סיסמה חדשה? מכשירים שמוגדרים עם הסיסמה הקודמת יפסיקו לגלוש עד שתעדכן אותם.')) {
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await bindingsApi.rotateProxyCredentials();
      setCreds({ ...res, has_password: true });
      setNewPassword(res.password || null);
    } catch {
      setError('יצירת הסיסמה נכשלה – נסה שוב');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        פרטי התחברות אישיים לפרוקסי (מומלץ)
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        הגדר במכשיר (הגדרות רשת → פרוקסי) את הכתובת והפורט, ובפעם הראשונה שהדפדפן יבקש – את שם המשתמש והסיסמה.
        כך הסינון מזהה אותך גם כשכמה בתים גולשים מאותה כתובת IP, ואין צורך בחיבור מכשיר לפי IP.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {creds && (
        <Stack spacing={1} sx={{ mb: 2 }}>
          {creds.proxy_host && <Row label="כתובת פרוקסי" value={creds.proxy_host} />}
          <Row label="פורט" value={String(creds.proxy_port)} />
          {creds.username && <Row label="שם משתמש" value={creds.username} />}
          {newPassword && <Row label="סיסמה" value={newPassword} />}
        </Stack>
      )}
      {newPassword && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          שמור את הסיסמה עכשיו – היא לא תוצג שוב. אם תאבד אותה, צור סיסמה חדשה.
        </Alert>
      )}
      <Box>
        <Button variant="contained" onClick={rotate} disabled={busy || !creds}>
          {creds?.has_password ? 'צור סיסמה חדשה' : 'צור פרטי התחברות'}
        </Button>
      </Box>
    </Paper>
  );
};

export default ProxyCredentialsCard;
