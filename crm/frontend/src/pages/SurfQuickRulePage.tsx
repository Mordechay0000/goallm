/**
 * Admin page opened from the surf widget ("החל"): shows the requested rule and applies it only after an
 * explicit click. The widget no longer carries any token – the action uses the admin's normal CRM login,
 * and opening a crafted link alone cannot change rules (the confirmation click is required).
 * Query: url=...&action=allow|block&scope=domain_only|domain_and_subdomains|exact_url
 */
import React, { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Alert, Box, Button, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import { adminApi } from '../api/admin';

type Action = 'allow' | 'block';
type Scope = 'domain_only' | 'domain_and_subdomains' | 'exact_url';

const SCOPE_LABELS: Record<Scope, string> = {
  domain_only: 'רק הדומיין',
  domain_and_subdomains: 'דומיין + תת-דומיינים',
  exact_url: 'כתובת ישירה',
};

const SurfQuickRulePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const params = useMemo(() => {
    const url = searchParams.get('url')?.trim() || '';
    const action = searchParams.get('action') as Action | null;
    const scope = searchParams.get('scope') as Scope | null;
    const valid =
      !!url && (action === 'allow' || action === 'block') && !!scope && scope in SCOPE_LABELS;
    return { url, action, scope, valid };
  }, [searchParams]);

  const apply = async () => {
    if (!params.valid || !params.action || !params.scope) return;
    setStatus('loading');
    try {
      const res = await adminApi.surfQuickRule(params.url, params.action, params.scope);
      setStatus('ok');
      setMessage(res.rule_display || 'הכלל נשמר.');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setStatus('error');
      setMessage(ax?.response?.data?.detail || ax?.message || 'שגיאה בשמירת הכלל');
    }
  };

  if (!params.valid) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">קישור לא תקין: חסרים פרמטרים (url, action, scope).</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, maxWidth: 560 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          אישור כלל גלובלי מסרגל הגלישה
        </Typography>
        <Stack spacing={1} sx={{ mb: 3 }}>
          <Typography>
            <strong>פעולה:</strong> {params.action === 'block' ? 'חסימה' : 'פתיחה'}
          </Typography>
          <Typography>
            <strong>היקף:</strong> {params.scope ? SCOPE_LABELS[params.scope] : ''}
          </Typography>
          <Typography sx={{ wordBreak: 'break-all' }}>
            <strong>כתובת:</strong> {params.url}
          </Typography>
        </Stack>
        {params.action === 'allow' && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            פתיחה ברשימה הגלובלית חלה על כל המשתמשים במערכת.
          </Alert>
        )}
        {status === 'ok' && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
        {status === 'error' && <Alert severity="error" sx={{ mb: 2 }}>{message}</Alert>}
        <Stack direction="row" spacing={2}>
          <Button
            variant="contained"
            color={params.action === 'block' ? 'error' : 'success'}
            onClick={apply}
            disabled={status === 'loading' || status === 'ok'}
          >
            {status === 'loading' ? <CircularProgress size={20} /> : 'אשר והחל'}
          </Button>
          <Button variant="outlined" onClick={() => window.close()}>
            סגור
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
};

export default SurfQuickRulePage;
