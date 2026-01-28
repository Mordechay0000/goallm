/**
 * Registration page. Phone required (login is always by phone). Avatar: upload image.
 * Live validation while typing.
 */
import React, { useState, useRef, useCallback } from 'react';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Avatar,
  Alert,
  InputAdornment,
} from '@mui/material';
import { Phone as PhoneIcon, CloudUpload as UploadIcon } from '@mui/icons-material';
import { useAuthStore } from '../store/authStore';
import { useNavigate } from 'react-router-dom';
import { PasswordField } from '../components/PasswordField';
import { FormErrors } from '../components/FormErrors';

const ALLOWED = 'image/jpeg,image/png,image/gif,image/webp';
const MAX_MB = 5;

const RegisterPage: React.FC = () => {
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

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.email) {
      newErrors.email = 'אימייל הוא שדה חובה';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'כתובת אימייל לא תקינה';
    }

    if (!formData.password) {
      newErrors.password = 'סיסמה היא שדה חובה';
    } else if (formData.password.length < 8) {
      newErrors.password = 'סיסמה חייבת להכיל לפחות 8 תווים';
    } else if (formData.password.length > 128) {
      newErrors.password = 'סיסמה לא יכולה להכיל יותר מ-128 תווים';
    } else if (!/\d/.test(formData.password)) {
      newErrors.password = 'סיסמה חייבת להכיל לפחות ספרה אחת';
    } else if (!/[a-zA-Zא-ת]/.test(formData.password)) {
      newErrors.password = 'סיסמה חייבת להכיל לפחות אות אחת';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'סיסמאות לא תואמות';
    }

    if (!formData.first_name?.trim()) {
      newErrors.first_name = 'שם פרטי הוא שדה חובה';
    } else if (formData.first_name.length > 100) {
      newErrors.first_name = 'שם פרטי לא יכול להכיל יותר מ-100 תווים';
    }

    if (!formData.last_name?.trim()) {
      newErrors.last_name = 'שם משפחה הוא שדה חובה';
    } else if (formData.last_name.length > 100) {
      newErrors.last_name = 'שם משפחה לא יכול להכיל יותר מ-100 תווים';
    }

    const ph = (formData.phone || '').replace(/\D/g, '');
    if (ph.length < 9) {
      newErrors.phone = 'מספר טלפון חובה (לפחות 9 ספרות). ההתחברות מתבצעת באמצעות טלפון וסיסמה';
    } else if (!/^[0-9\-\+\s\(\)]+$/.test(formData.phone)) {
      newErrors.phone = 'מספר טלפון לא תקין';
    }

    if (avatarFile && avatarFile.size > MAX_MB * 1024 * 1024) {
      newErrors.avatar = `גודל התמונה עד ${MAX_MB}MB`;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

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

  return (
    <Container maxWidth="sm" sx={{ mt: 4, mb: 4 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h4" align="center" gutterBottom>
          הרשמה למערכת
        </Typography>

        <Alert
          severity="info"
          icon={<PhoneIcon />}
          sx={{ mb: 3, fontWeight: 600, '& .MuiAlert-message': { width: '100%' } }}
        >
          ההתחברות מתבצעת תמיד באמצעות <strong>טלפון וסיסמה</strong>. וודא שמספר הטלפון תקין.
        </Alert>

        <form onSubmit={handleSubmit} noValidate>
          <FormErrors errors={formErrors} />

          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
            <Avatar
              src={avatarPreview || undefined}
              sx={{ width: 100, height: 100, mb: 2 }}
            >
              {formData.first_name?.[0] || formData.last_name?.[0] || '?'}
            </Avatar>
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED}
              onChange={handleAvatarChange}
              style={{ display: 'none' }}
            />
            <Button
              variant="outlined"
              startIcon={<UploadIcon />}
              onClick={() => fileInputRef.current?.click()}
              sx={{ mb: 1 }}
            >
              העלאת תמונה
            </Button>
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
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateFirstNameLive(formData.first_name);
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
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateLastNameLive(formData.last_name);
              setErrors((prev) => (err ? { ...prev, last_name: err } : (() => { const n = { ...prev }; delete n.last_name; return n; })()));
            }}
            error={!!errors.last_name}
            helperText={errors.last_name}
            sx={{ mb: 2 }}
          />
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
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateEmailLive(formData.email);
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
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validatePhoneLive(formData.phone);
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
          <PasswordField
            label="סיסמה"
            value={formData.password}
            onChange={(v) => {
              setFormData({ ...formData, password: v });
              const err = validatePasswordLive(v);
              setErrors((prev) => (err ? { ...prev, password: err } : (() => { const n = { ...prev }; delete n.password; return n; })()));
              // Also validate confirm password if it has a value
              if (formData.confirmPassword) {
                const confirmErr = validateConfirmPasswordLive(formData.confirmPassword, v);
                setErrors((prev) => (confirmErr ? { ...prev, confirmPassword: confirmErr } : (() => { const n = { ...prev }; delete n.confirmPassword; return n; })()));
              }
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validatePasswordLive(formData.password);
              setErrors((prev) => (err ? { ...prev, password: err } : (() => { const n = { ...prev }; delete n.password; return n; })()));
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
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateConfirmPasswordLive(formData.confirmPassword, formData.password);
              setErrors((prev) => (err ? { ...prev, confirmPassword: err } : (() => { const n = { ...prev }; delete n.confirmPassword; return n; })()));
            }}
            required
            error={!!errors.confirmPassword}
            helperText={errors.confirmPassword}
            sx={{ mb: 3 }}
          />
          <Button type="submit" fullWidth variant="contained" size="large" disabled={loading}>
            הירשם
          </Button>
          <Box sx={{ mt: 2, textAlign: 'center' }}>
            <Button variant="text" onClick={() => navigate('/login')} size="small">
              כבר יש לך חשבון? התחבר
            </Button>
          </Box>
        </form>
      </Paper>
    </Container>
  );
};

export default RegisterPage;
