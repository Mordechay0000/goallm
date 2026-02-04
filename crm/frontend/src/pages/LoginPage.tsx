/**
 * Login: אימות טלפוני (ברירת מחדל) או התחברות בסיסמה.
 * כפתורים פעילים רק כשיש פרטים תקינים. ולידציה תוך כדי הקלדה.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
} from '@mui/material';
import { useAuthStore } from '../store/authStore';
import { authApi } from '../api/auth';
import { useNavigate, useLocation } from 'react-router-dom';
import { PasswordField } from '../components/PasswordField';
import { FormErrors } from '../components/FormErrors';

type LoginMode = 'phone' | 'password';

function normalizePhone(s: string): string {
  return (s || '').replace(/\D/g, '');
}

const LoginPage: React.FC = () => {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'request' | 'verify'>('request');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const { login, loginWithPhoneCode } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const registrationMessage = location.state?.message as string | undefined;
  const redirectTo = new URLSearchParams(location.search).get('redirect') || '/';

  const mode: LoginMode = password.length > 0 ? 'password' : 'phone';

  const ph = normalizePhone(phone);
  const phoneValid = ph.length >= 9;
  const passwordValid = password.length > 0;
  const codeValid = code.length === 6 && /^\d+$/.test(code);

  useEffect(() => {
    if (registrationMessage) {
      window.history.replaceState({}, document.title);
    }
  }, [registrationMessage]);

  const validatePhoneLive = useCallback((value: string) => {
    const n = normalizePhone(value);
    if (n.length === 0) return undefined;
    if (n.length < 9) return 'נא להזין מספר טלפון תקין (לפחות 9 ספרות)';
    return undefined;
  }, []);

  const validatePasswordLive = useCallback((value: string) => {
    if (value.length === 0) return 'נא להזין סיסמה';
    return undefined;
  }, []);

  const validateCodeLive = useCallback((value: string) => {
    if (value.length === 0) return undefined;
    if (value.length !== 6 || !/^\d+$/.test(value)) return 'הקוד הוא 6 ספרות בדיוק';
    return undefined;
  }, []);

  const setPhoneAndValidate = (value: string) => {
    setPhone(value);
    const e = validatePhoneLive(value);
    setErrors((prev) => (e != null ? { ...prev, phone: e } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
    setFormErrors((prev) => (prev.length ? [] : prev));
  };

  const setPasswordAndValidate = (value: string) => {
    setPassword(value);
    if (value.length === 0) {
      setCode('');
      setStep('request');
      setErrors((prev) => { const n = { ...prev }; delete n.password; delete n.code; return n; });
    } else {
      const e = validatePasswordLive(value);
      setErrors((prev) => (e != null ? { ...prev, password: e } : (() => { const n = { ...prev }; delete n.password; return n; })()));
    }
    setFormErrors((prev) => (prev.length ? [] : prev));
  };

  const setCodeAndValidate = (value: string) => {
    const v = value.replace(/\D/g, '').slice(0, 6);
    setCode(v);
    const e = validateCodeLive(v);
    setErrors((prev) => (e != null ? { ...prev, code: e } : (() => { const n = { ...prev }; delete n.code; return n; })()));
    setFormErrors((prev) => (prev.length ? [] : prev));
  };

  const helperText =
    mode === 'phone'
      ? 'אם יש לך סיסמה – הזן אותה בשדה סיסמה למטה'
      : 'אם אין לך סיסמה – השאר את השדה ריק ונשלח קוד לטלפון';

  const handleRequestCode = async () => {
    if (!phoneValid || step !== 'request') return;
    setLoading(true);
    setFormErrors([]);
    try {
      await authApi.requestPhoneCode(phone);
      setStep('verify');
      setErrors((prev) => { const n = { ...prev }; delete n.phone; return n; });
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string | { msg?: string; message?: string }[] } }; message?: string };
      const raw = ax?.response?.data?.detail ?? (err instanceof Error ? err.message : undefined) ?? 'שליחת הקוד נכשלה';
      const formErr = Array.isArray(raw) ? (raw as { msg?: string; message?: string }[]).map((x) => x?.msg || x?.message || '') : [typeof raw === 'string' ? raw : String(raw)];
      setFormErrors(formErr);
      setErrors((prev) => (typeof raw === 'string' ? { ...prev, phone: raw } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyPhone = async () => {
    if (!phoneValid || !codeValid || step !== 'verify') return;
    setLoading(true);
    setFormErrors([]);
    try {
      await loginWithPhoneCode(phone, code);
      navigate(redirectTo, { replace: true });
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string | { msg?: string; message?: string }[] } }; message?: string };
      const raw = ax?.response?.data?.detail ?? (err instanceof Error ? err.message : undefined) ?? 'אימות הקוד נכשל';
      const formErr = Array.isArray(raw) ? (raw as { msg?: string; message?: string }[]).map((x) => x?.msg || x?.message || '') : [typeof raw === 'string' ? raw : String(raw)];
      setFormErrors(formErr);
      setErrors((prev) => (typeof raw === 'string' ? { ...prev, code: raw } : (() => { const n = { ...prev }; delete n.code; return n; })()));
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneValid || !passwordValid || mode !== 'password') return;
    setLoading(true);
    setFormErrors([]);
    try {
      await login(phone, password);
      navigate(redirectTo, { replace: true });
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string | { msg?: string; message?: string }[] } }; message?: string };
      const raw = ax?.response?.data?.detail ?? (err instanceof Error ? err.message : undefined) ?? 'התחברות נכשלה';
      const formErr = Array.isArray(raw) ? (raw as { msg?: string; message?: string }[]).map((x) => x?.msg || x?.message || '') : [typeof raw === 'string' ? raw : String(raw)];
      setFormErrors(formErr);
      setErrors((prev) => (typeof raw === 'string' ? { ...prev, password: raw } : (() => { const n = { ...prev }; delete n.password; return n; })()));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8, mb: 4 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h5" align="center" gutterBottom sx={{ fontWeight: 600, mb: 4 }}>
          כניסה לחשבון שלי
        </Typography>

        {registrationMessage && (
          <Alert severity="success" sx={{ mb: 3 }}>
            {registrationMessage}
          </Alert>
        )}

        <FormErrors errors={formErrors} />

        <form onSubmit={handlePasswordLogin} noValidate>
          <TextField
            fullWidth
            label="טלפון"
            required
            value={phone}
            onChange={(e) => setPhoneAndValidate(e.target.value)}
            onBlur={() => {
              const e = validatePhoneLive(phone);
              setErrors((prev) => (e != null ? { ...prev, phone: e } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
            }}
            error={!!errors.phone}
            helperText={errors.phone || 'נכנסים עם הטלפון והסיסמה (או עם קוד שנשלח לטלפון)'}
            placeholder="050-1234567"
            sx={{ mb: 2 }}
            inputProps={{ inputMode: 'tel' }}
          />

          {mode === 'phone' && step === 'verify' && (
            <TextField
              fullWidth
              label="קוד אימות"
              required
              value={code}
              onChange={(e) => setCodeAndValidate(e.target.value)}
              onBlur={() => {
                const e = validateCodeLive(code);
                setErrors((prev) => (e != null ? { ...prev, code: e } : (() => { const n = { ...prev }; delete n.code; return n; })()));
              }}
              error={!!errors.code}
              helperText={errors.code || 'הקוד בן 6 ספרות שקיבלת בהודעה'}
              placeholder="123456"
              sx={{ mb: 2 }}
              inputProps={{ inputMode: 'numeric', maxLength: 6 }}
            />
          )}

          <PasswordField
            label="סיסמה"
            value={password}
            onChange={(v) => setPasswordAndValidate(v)}
            error={!!errors.password}
            helperText={errors.password || helperText}
            required={false}
            sx={{ mb: 2 }}
          />

          {mode === 'phone' && (
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              {step === 'request' ? (
                <Button
                  type="button"
                  fullWidth
                  variant="contained"
                  size="large"
                  disabled={loading || !phoneValid}
                  onClick={handleRequestCode}
                >
                  שלח לי קוד לטלפון
                </Button>
              ) : (
                <Button
                  type="button"
                  fullWidth
                  variant="contained"
                  size="large"
                  disabled={loading || !phoneValid || !codeValid}
                  onClick={handleVerifyPhone}
                >
                  נכנס עם הקוד
                </Button>
              )}
            </Box>
          )}

          {mode === 'password' && (
            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading || !phoneValid || !passwordValid}
              sx={{ mb: 3 }}
            >
              נכנס עם הסיסמה
            </Button>
          )}

          <Box sx={{ textAlign: 'center' }}>
            <Button variant="text" onClick={() => navigate('/register')} size="small">
              עדיין אין לי חשבון – אני רוצה ליצור אחד
            </Button>
          </Box>
        </form>
      </Paper>
    </Container>
  );
};

export default LoginPage;
