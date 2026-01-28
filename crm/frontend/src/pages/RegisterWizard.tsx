/**
 * Registration Wizard - Multi-step registration process
 * Minimal, functional design
 */
import React, { useState, useRef, useCallback } from 'react';
import {
  Container,
  Paper,
  TextField,
  Typography,
  Box,
  Avatar,
  InputAdornment,
} from '@mui/material';
import { Phone as PhoneIcon } from '@mui/icons-material';
import { useAuthStore } from '../store/authStore';
import { useNavigate } from 'react-router-dom';
import { PasswordField } from '../components/PasswordField';
import { FormErrors } from '../components/FormErrors';
import Stepper from '../components/Stepper';

const ALLOWED = 'image/jpeg,image/png,image/gif,image/webp';
const MAX_MB = 5;

const RegisterWizard: React.FC = () => {
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
  const { register } = useAuthStore();
  const navigate = useNavigate();

  // Live validation functions
  const validateEmailLive = useCallback((value: string): string | undefined => {
    if (value.length === 0) return 'אימייל הוא שדה חובה';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'כתובת אימייל לא תקינה';
    return undefined;
  }, []);

  const validatePasswordLive = useCallback((value: string): string | undefined => {
    if (value.length === 0) return 'סיסמה היא שדה חובה';
    if (value.length < 8) return 'סיסמה חייבת להכיל לפחות 8 תווים';
    if (value.length > 128) return 'סיסמה לא יכולה להכיל יותר מ-128 תווים';
    if (!/\d/.test(value)) return 'סיסמה חייבת להכיל לפחות ספרה אחת';
    if (!/[a-zA-Zא-ת]/.test(value)) return 'סיסמה חייבת להכיל לפחות אות אחת';
    return undefined;
  }, []);

  const validateConfirmPasswordLive = useCallback((value: string, password: string): string | undefined => {
    if (value.length === 0) return 'אימות סיסמה הוא שדה חובה';
    if (value !== password) return 'סיסמאות לא תואמות';
    return undefined;
  }, []);

  const validateFirstNameLive = useCallback((value: string): string | undefined => {
    if (!value.trim()) return 'שם פרטי הוא שדה חובה';
    if (value.length > 100) return 'שם פרטי לא יכול להכיל יותר מ-100 תווים';
    return undefined;
  }, []);

  const validateLastNameLive = useCallback((value: string): string | undefined => {
    if (!value.trim()) return 'שם משפחה הוא שדה חובה';
    if (value.length > 100) return 'שם משפחה לא יכול להכיל יותר מ-100 תווים';
    return undefined;
  }, []);

  const validatePhoneLive = useCallback((value: string): string | undefined => {
    const ph = (value || '').replace(/\D/g, '');
    if (ph.length === 0) return 'מספר טלפון חובה (לפחות 9 ספרות). ההתחברות מתבצעת באמצעות טלפון וסיסמה';
    if (ph.length < 9) return 'מספר טלפון חובה (לפחות 9 ספרות). ההתחברות מתבצעת באמצעות טלפון וסיסמה';
    if (!/^[0-9\-\+\s\(\)]+$/.test(value)) return 'מספר טלפון לא תקין';
    return undefined;
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
      navigate('/login', {
        state: { message: 'הרשמה הושלמה! התחבר עם הטלפון והסיסמה שלך.' },
      });
    } catch (error: any) {
      let msg = 'שגיאה בהרשמה';
      const detail = error.response?.data?.detail;
      if (Array.isArray(detail) && detail[0]) msg = detail[0].msg || detail[0].message || msg;
      else if (typeof detail === 'string') msg = detail;
      else if (error.message) msg = error.message;
      setFormErrors([msg]);
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.type.startsWith('image/') || !ALLOWED.includes(f.type)) {
      setErrors((prev) => ({ ...prev, avatar: 'רק תמונות: JPG, PNG, GIF, WEBP' }));
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
      label: 'פרטים אישיים',
      description: 'הזן את הפרטים האישיים שלך',
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
      label: 'פרטי התחברות',
      description: 'מספר טלפון ואימייל - ההתחברות מתבצעת באמצעות טלפון וסיסמה',
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
            value={formData.phone}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, phone: v });
              const err = validatePhoneLive(v);
              setErrors((prev) => (err ? { ...prev, phone: err } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
            }}
            error={!!errors.phone}
            helperText={errors.phone || 'ההתחברות מתבצעת באמצעות טלפון וסיסמה. לדוגמה: 050-1234567'}
            placeholder="050-1234567"
            sx={{ mb: 2 }}
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
      label: 'אבטחה',
      description: 'הגדר סיסמה חזקה לחשבון שלך',
      content: (
        <Box>
          <PasswordField
            label="סיסמה"
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
            helperText={errors.password || 'מינימום 8 תווים, ספרה ואות'}
            sx={{ mb: 2 }}
          />
          <PasswordField
            label="אימות סיסמה"
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
          />
        </Box>
      ),
    },
  ];

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h5" component="h1" gutterBottom sx={{ mb: 4, fontWeight: 600 }}>
          הרשמה למערכת
        </Typography>

        <Stepper
          steps={steps}
          activeStep={activeStep}
          onNext={handleNext}
          onBack={handleBack}
          onFinish={handleFinish}
          nextLabel="הבא"
          backLabel="חזור"
          finishLabel={loading ? 'מעבד...' : 'סיום והרשמה'}
        />
      </Paper>
    </Container>
  );
};

export default RegisterWizard;
