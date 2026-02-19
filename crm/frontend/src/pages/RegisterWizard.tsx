/**
 * Registration Wizard - Multi-step registration process
 * Minimal, functional design
 */
import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Container,
  Paper,
  TextField,
  Typography,
  Box,
  Avatar,
  InputAdornment,
  Button,
} from '@mui/material';
import { Phone as PhoneIcon } from '@mui/icons-material';
import { useAuthStore } from '../store/authStore';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { PasswordField } from '../components/PasswordField';
import { FormErrors } from '../components/FormErrors';
import Stepper from '../components/Stepper';
import { validatePhone } from '../utils/validation';

const ALLOWED = 'image/jpeg,image/png,image/gif,image/webp';
const MAX_MB = 5;

export interface RegisterWizardSetupMode {
  title: string;
  subtitle: string;
  successMessage: string;
}

interface RegisterWizardProps {
  /** When set, show first-time admin setup UI and redirect to /login with successMessage after register */
  setupMode?: RegisterWizardSetupMode;
}

const RegisterWizard: React.FC<RegisterWizardProps> = ({ setupMode }) => {
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    phone: '',
  });
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const { register, logout, isAuthenticated } = useAuthStore();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTo = setupMode ? '/login' : (searchParams.get('redirect') || '/login');
  const isBindFlow = !setupMode && redirectTo.includes('/bind') && (redirectTo.includes('from_login=1') || redirectTo.includes('from_login%3D1'));

  // When coming from bind flow while already logged in: disconnect from current account so the new registration binds the device to the new account
  useEffect(() => {
    if (isBindFlow && isAuthenticated) {
      logout();
    }
  }, [isBindFlow, isAuthenticated, logout]);

  // Live validation functions
  const validateEmailLive = useCallback((value: string): string | undefined => {
    if (value.length === 0) return 'נא להזין אימייל';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'נא להזין כתובת אימייל תקינה';
    return undefined;
  }, []);

  const validatePasswordLive = useCallback((value: string): string | undefined => {
    if (value.length === 0) return 'נא להזין סיסמה';
    if (value.length < 8) return 'הסיסמה צריכה לפחות 8 תווים';
    if (value.length > 128) return 'הסיסמה ארוכה מדי';
    if (!/\d/.test(value)) return 'הסיסמה צריכה לכלול לפחות ספרה אחת';
    if (!/[a-zA-Zא-ת]/.test(value)) return 'הסיסמה צריכה לכלול לפחות אות אחת';
    return undefined;
  }, []);

  const validateConfirmPasswordLive = useCallback((value: string, password: string): string | undefined => {
    if (value.length === 0) return 'נא להזין שוב את הסיסמה';
    if (value !== password) return 'הסיסמאות לא זהות';
    return undefined;
  }, []);

  const validateFirstNameLive = useCallback((value: string): string | undefined => {
    if (!value.trim()) return 'נא להזין שם פרטי';
    if (value.length > 100) return 'השם ארוך מדי';
    return undefined;
  }, []);

  const validateLastNameLive = useCallback((value: string): string | undefined => {
    if (!value.trim()) return 'נא להזין שם משפחה';
    if (value.length > 100) return 'השם ארוך מדי';
    return undefined;
  }, []);

  const validatePhoneLive = useCallback((value: string): string | undefined => {
    if (!(value || '').trim()) {
      return 'נא להזין מספר טלפון (ישראל: 10 ספרות שמתחילות ב־05, או מספר בינלאומי שמתחיל ב־+)';
    }
    const err = validatePhone(value);
    return err || undefined;
  }, []);

  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {};

    if (step === 0) {
      // Personal info
      const firstNameErr = validateFirstNameLive(formData.first_name);
      const lastNameErr = validateLastNameLive(formData.last_name);
      if (firstNameErr) newErrors.first_name = firstNameErr;
      if (lastNameErr) newErrors.last_name = lastNameErr;
    } else if (step === 1) {
      // Contact info
      const emailErr = validateEmailLive(formData.email);
      const phoneErr = validatePhoneLive(formData.phone);
      if (emailErr) newErrors.email = emailErr;
      if (phoneErr) newErrors.phone = phoneErr;
    } else if (step === 2) {
      // Security
      const passwordErr = validatePasswordLive(formData.password);
      const confirmErr = validateConfirmPasswordLive(formData.confirmPassword, formData.password);
      if (passwordErr) newErrors.password = passwordErr;
      if (confirmErr) newErrors.confirmPassword = confirmErr;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(activeStep)) {
      setActiveStep((prev) => prev + 1);
      setFormErrors([]);
    }
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
    setFormErrors([]);
  };

  const handleFinish = async () => {
    if (!validateStep(activeStep)) return;

    setLoading(true);
    setFormErrors([]);
    try {
      await register({
        email: formData.email.trim(),
        password: formData.password,
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        phone: formData.phone.trim(),
        avatar: avatarFile || undefined,
      });
      const loginUrl = redirectTo.startsWith('/') ? `/login?redirect=${encodeURIComponent(redirectTo)}` : '/login';
      const successMessage = setupMode
        ? setupMode.successMessage
        : isBindFlow
          ? 'החשבון החדש נוצר! עכשיו היכנס עם הטלפון והסיסמה שבחרת – ואז נחבר את המכשיר לחשבון הזה.'
          : 'החשבון נוצר! עכשיו אפשר להיכנס עם הטלפון והסיסמה שבחרת.';
      navigate(loginUrl, { state: { message: successMessage } });
    } catch (error: unknown) {
      let msg = 'משהו השתבש – נסה שוב או פנה לתמיכה';
      const ax = error as { response?: { data?: { detail?: string | { msg?: string; message?: string }[] } }; message?: string };
      const detail = ax?.response?.data?.detail;
      if (Array.isArray(detail) && detail[0]) msg = detail[0].msg || detail[0].message || msg;
      else if (typeof detail === 'string') msg = detail;
      else if (ax?.message) msg = ax.message;
      setFormErrors([msg]);
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.type.startsWith('image/') || !ALLOWED.includes(f.type)) {
      setErrors((prev) => ({ ...prev, avatar: 'רק תמונות: JPG, PNG, GIF, WEBP, BMP' }));
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setErrors((prev) => ({ ...prev, avatar: `גודל עד ${MAX_MB}MB` }));
      return;
    }
    setAvatarFile(f);
    setAvatarPreview(URL.createObjectURL(f));
    setErrors((prev) => { const n = { ...prev }; delete n.avatar; return n; });
  };

  const steps = [
    {
      label: 'מי אני',
      description: 'שם ותמונת פרופיל (לא חובה)',
      content: (
        <Box>
          <FormErrors errors={formErrors} />
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
            <Box sx={{ position: 'relative', mb: 2 }}>
              <Avatar
                src={avatarPreview || undefined}
                sx={{ width: 80, height: 80, cursor: avatarPreview ? 'pointer' : 'default' }}
                onClick={() => fileInputRef.current?.click()}
              >
                {formData.first_name?.[0] || formData.last_name?.[0] || '?'}
              </Avatar>
              {avatarPreview && (
                <Box
                  onClick={() => {
                    setAvatarFile(null);
                    setAvatarPreview(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                    setErrors((prev) => { const n = { ...prev }; delete n.avatar; return n; });
                  }}
                  sx={{
                    position: 'absolute',
                    top: -8,
                    right: -8,
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    bgcolor: 'error.main',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                >
                  ×
                </Box>
              )}
            </Box>
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED}
              onChange={handleAvatarChange}
              style={{ display: 'none' }}
            />
            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                style={{
                  padding: '6px 12px',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  background: 'white',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                {avatarPreview ? 'החלף תמונה' : 'העלאת תמונה'}
              </button>
            </Box>
            {errors.avatar && (
              <Typography variant="caption" color="error">
                {errors.avatar}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary">
              JPG, PNG, GIF או WEBP עד {MAX_MB}MB
            </Typography>
          </Box>

          <TextField
            fullWidth
            label="שם פרטי"
            required
            value={formData.first_name}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, first_name: v });
              const err = validateFirstNameLive(v);
              setErrors((prev) => (err ? { ...prev, first_name: err } : (() => { const n = { ...prev }; delete n.first_name; return n; })()));
            }}
            error={!!errors.first_name}
            helperText={errors.first_name}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="שם משפחה"
            required
            value={formData.last_name}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, last_name: v });
              const err = validateLastNameLive(v);
              setErrors((prev) => (err ? { ...prev, last_name: err } : (() => { const n = { ...prev }; delete n.last_name; return n; })()));
            }}
            error={!!errors.last_name}
            helperText={errors.last_name}
            sx={{ mb: 2 }}
          />
        </Box>
      ),
    },
    {
      label: 'איך ניצור קשר',
      description: 'טלפון ואימייל – נכנסים עם הטלפון והסיסמה',
      content: (
        <Box>
          <TextField
            fullWidth
            label="אימייל"
            type="email"
            required
            value={formData.email}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, email: v });
              const err = validateEmailLive(v);
              setErrors((prev) => (err ? { ...prev, email: err } : (() => { const n = { ...prev }; delete n.email; return n; })()));
            }}
            error={!!errors.email}
            helperText={errors.email}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="טלפון"
            required
            name="phone"
            value={formData.phone}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, phone: v });
              const err = validatePhoneLive(v);
              setErrors((prev) => (err ? { ...prev, phone: err } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
            }}
            error={!!errors.phone}
            helperText={errors.phone || 'נכנסים עם הטלפון והסיסמה. לדוגמה: 050-1234567'}
            placeholder="050-1234567"
            sx={{ mb: 2 }}
            autoComplete="tel"
            inputProps={{ inputMode: 'tel' }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <PhoneIcon color="action" />
                </InputAdornment>
              ),
            }}
          />
        </Box>
      ),
    },
    {
      label: 'סיסמה',
      description: 'בחר סיסמה שתשתמש בה לכניסה',
      content: (
        <Box>
          <PasswordField
            label="סיסמה"
            name="new-password"
            value={formData.password}
            onChange={(v) => {
              setFormData({ ...formData, password: v });
              const err = validatePasswordLive(v);
              setErrors((prev) => (err ? { ...prev, password: err } : (() => { const n = { ...prev }; delete n.password; return n; })()));
              if (formData.confirmPassword) {
                const confirmErr = validateConfirmPasswordLive(formData.confirmPassword, v);
                setErrors((prev) => (confirmErr ? { ...prev, confirmPassword: confirmErr } : (() => { const n = { ...prev }; delete n.confirmPassword; return n; })()));
              }
            }}
            required
            error={!!errors.password}
            helperText={errors.password || 'לפחות 8 תווים, עם ספרה ואות'}
            sx={{ mb: 2 }}
            autoComplete="new-password"
          />
          <PasswordField
            label="אימות סיסמה"
            name="confirm-password"
            value={formData.confirmPassword}
            onChange={(v) => {
              setFormData({ ...formData, confirmPassword: v });
              const err = validateConfirmPasswordLive(v, formData.password);
              setErrors((prev) => (err ? { ...prev, confirmPassword: err } : (() => { const n = { ...prev }; delete n.confirmPassword; return n; })()));
            }}
            required
            error={!!errors.confirmPassword}
            helperText={errors.confirmPassword}
            sx={{ mb: 2 }}
            autoComplete="new-password"
          />
        </Box>
      ),
    },
  ];

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Enter') return;
    const target = e.target as HTMLElement;
    if (target.tagName === 'TEXTAREA') return;
    e.preventDefault();
    if (activeStep === steps.length - 1) {
      if (validateStep(activeStep)) handleFinish();
    } else {
      handleNext();
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }} className="page-section" onKeyDown={handleKeyDown}>
      <Paper className="paper-form" sx={{ p: { xs: 2, sm: 4 } }}>
        <Box className="page-title-section" sx={{ mb: setupMode ? 1 : 3 }}>
          <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
            {setupMode ? setupMode.title : 'יצירת חשבון חדש'}
          </Typography>
          {setupMode && (
            <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
              {setupMode.subtitle}
            </Typography>
          )}
        </Box>

        <Stepper
          steps={steps}
          activeStep={activeStep}
          onNext={handleNext}
          onBack={handleBack}
          onFinish={handleFinish}
          nextLabel="הבא"
          backLabel="חזור"
          finishLabel={loading ? 'יוצר חשבון...' : 'סיום – ליצור את החשבון'}
        />
        {!setupMode && (
          <Box sx={{ textAlign: 'center', mt: 3 }}>
            <Button variant="text" size="small" onClick={() => navigate(redirectTo.startsWith('/') ? `/login?redirect=${encodeURIComponent(redirectTo)}` : '/login')}>
              כבר יש לי חשבון – אני רוצה להיכנס
            </Button>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default RegisterWizard;
