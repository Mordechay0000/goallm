/**
 * Profile edit page. Avatar: upload image (no URL).
 * Live validation while typing.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Avatar,
  Divider,
  Alert,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, CloudUpload as UploadIcon } from '@mui/icons-material';
import { useAuthStore } from '../store/authStore';
import { authApi, getAvatarUrl } from '../api/auth';
import type { UserUpdate, PasswordChange } from '../api/auth';
import { PasswordField } from '../components/PasswordField';
import { FormErrors } from '../components/FormErrors';

const ALLOWED = 'image/jpeg,image/png,image/gif,image/webp';
const MAX_MB = 5;

const ProfileEditPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, refreshProfile } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string>('');
  
  const [formData, setFormData] = useState<UserUpdate>({
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
  });
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [passwordData, setPasswordData] = useState<PasswordChange & { confirm_password?: string }>({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [passwordErrors, setPasswordErrors] = useState<Record<string, string>>({});
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const [passwordFormErrors, setPasswordFormErrors] = useState<string[]>([]);

  // Live validation functions for profile
  const validateEmailLive = useCallback((value: string): string | undefined => {
    if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'כתובת אימייל לא תקינה';
    return undefined;
  }, []);

  const validateFirstNameLive = useCallback((value: string): string | undefined => {
    if (value && value.length > 100) return 'שם פרטי לא יכול להכיל יותר מ-100 תווים';
    return undefined;
  }, []);

  const validateLastNameLive = useCallback((value: string): string | undefined => {
    if (value && value.length > 100) return 'שם משפחה לא יכול להכיל יותר מ-100 תווים';
    return undefined;
  }, []);

  const validatePhoneLive = useCallback((value: string): string | undefined => {
    if (value && !/^[0-9+\s()-]+$/.test(value)) return 'מספר טלפון לא תקין';
    return undefined;
  }, []);

  // Live validation functions for password
  const validatePasswordLive = useCallback((value: string): string | undefined => {
    if (value.length === 0) return undefined; // Optional field
    if (value.length < 8) return 'סיסמה חייבת להכיל לפחות 8 תווים';
    if (value.length > 128) return 'סיסמה לא יכולה להכיל יותר מ-128 תווים';
    if (!/\d/.test(value)) return 'סיסמה חייבת להכיל לפחות ספרה אחת';
    if (!/[a-zA-Zא-ת]/.test(value)) return 'סיסמה חייבת להכיל לפחות אות אחת';
    return undefined;
  }, []);

  const validateConfirmPasswordLive = useCallback((value: string, password: string): string | undefined => {
    if (value.length === 0) return undefined; // Optional field
    if (value !== password) return 'סיסמאות לא תואמות';
    return undefined;
  }, []);

  useEffect(() => {
    loadProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, []);

  const loadProfile = async () => {
    try {
      const profile = await authApi.getProfile();
      await refreshProfile();
      setFormData({
        email: profile.email || '',
        first_name: profile.first_name || '',
        last_name: profile.last_name || '',
        phone: profile.phone || '',
      });
    } catch (error: unknown) {
      const ax = error as { response?: { data?: { detail?: string } }; message?: string };
      setFormErrors([ax?.response?.data?.detail || ax?.message || 'שגיאה בטעינת פרופיל']);
    }
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.type.startsWith('image/') || !ALLOWED.includes(f.type)) {
      setAvatarError('רק תמונות: JPG, PNG, GIF, WEBP');
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setAvatarError(`גודל עד ${MAX_MB}MB`);
      return;
    }
    setAvatarError(null);
    setAvatarLoading(true);
    try {
      await authApi.uploadAvatar(f);
      await refreshProfile();
      await loadProfile();
      setSuccessMessage('תמונת פרופיל עודכנה');
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setAvatarError(ax?.response?.data?.detail || ax?.message || 'שגיאה בהעלאת תמונה');
    } finally {
      setAvatarLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const validateProfileForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'כתובת אימייל לא תקינה';
    }

    if (formData.first_name && formData.first_name.length > 100) {
      newErrors.first_name = 'שם פרטי לא יכול להכיל יותר מ-100 תווים';
    }

    if (formData.last_name && formData.last_name.length > 100) {
      newErrors.last_name = 'שם משפחה לא יכול להכיל יותר מ-100 תווים';
    }

    if (formData.phone && !/^[0-9+\s()-]+$/.test(formData.phone)) {
      newErrors.phone = 'מספר טלפון לא תקין';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validatePasswordForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!passwordData.current_password) {
      newErrors.current_password = 'סיסמה נוכחית היא שדה חובה';
    }

    if (!passwordData.new_password) {
      newErrors.new_password = 'סיסמה חדשה היא שדה חובה';
    } else if (passwordData.new_password.length < 8) {
      newErrors.new_password = 'סיסמה חייבת להכיל לפחות 8 תווים';
    } else if (passwordData.new_password.length > 128) {
      newErrors.new_password = 'סיסמה לא יכולה להכיל יותר מ-128 תווים';
    } else if (!/\d/.test(passwordData.new_password)) {
      newErrors.new_password = 'סיסמה חייבת להכיל לפחות ספרה אחת';
    } else if (!/[a-zA-Zא-ת]/.test(passwordData.new_password)) {
      newErrors.new_password = 'סיסמה חייבת להכיל לפחות אות אחת';
    }

    if (passwordData.new_password !== passwordData.confirm_password) {
      newErrors.confirm_password = 'סיסמאות לא תואמות';
    }

    setPasswordErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateProfileForm()) {
      return;
    }

    setLoading(true);
    setSuccessMessage('');
    setFormErrors([]);
    
    try {
      await authApi.updateProfile(formData);
      await refreshProfile();
      setSuccessMessage('פרופיל עודכן בהצלחה');
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (error: unknown) {
      let msg = 'שגיאה בעדכון פרופיל';
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

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validatePasswordForm()) {
      return;
    }

    setPasswordLoading(true);
    setSuccessMessage('');
    setPasswordFormErrors([]);
    
    try {
      await authApi.changePassword({
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      });
      setSuccessMessage('סיסמה עודכנה בהצלחה');
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: '',
      });
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (error: unknown) {
      let msg = 'שגיאה בשינוי סיסמה';
      const ax = error as { response?: { data?: { detail?: string } }; message?: string };
      const detail = ax?.response?.data?.detail;
      if (typeof detail === 'string') msg = detail;
      else if (ax?.message) msg = ax.message;
      setPasswordFormErrors([msg]);
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/')}>
          חזרה
        </Button>
        <Typography variant="h4" component="h1" fontWeight="bold">
          עריכת פרופיל
        </Typography>
      </Box>

      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage('')}>
          {successMessage}
        </Alert>
      )}

      {/* Profile Information */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          פרטים אישיים
        </Typography>
        <Divider sx={{ my: 2 }} />

        <form onSubmit={handleProfileSubmit} noValidate>
          <FormErrors errors={formErrors} />
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
            <Box sx={{ position: 'relative', mb: 2 }}>
              <Avatar
                src={getAvatarUrl(user?.avatar_url)}
                sx={{ width: 100, height: 100, cursor: user?.avatar_url ? 'pointer' : 'default' }}
                onClick={() => fileInputRef.current?.click()}
              >
                {formData.first_name?.[0] || formData.last_name?.[0] || user?.email?.[0] || 'U'}
              </Avatar>
              {user?.avatar_url && (
                <Box
                  onClick={async () => {
                    try {
                      await authApi.updateProfile({ avatar_url: '' });
                      await refreshProfile();
                      await loadProfile();
                      setSuccessMessage('תמונת פרופיל נמחקה');
                      setTimeout(() => setSuccessMessage(''), 5000);
                    } catch (err: unknown) {
                      const a = err as { response?: { data?: { detail?: string } }; message?: string };
                      setAvatarError(a?.response?.data?.detail || a?.message || 'שגיאה במחיקת תמונה');
                    }
                  }}
                  sx={{
                    position: 'absolute',
                    top: -8,
                    right: -8,
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    bgcolor: 'error.main',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    fontSize: '1.2rem',
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
            <Button
              variant="outlined"
              startIcon={<UploadIcon />}
              onClick={() => fileInputRef.current?.click()}
              disabled={avatarLoading}
              sx={{ mb: 1 }}
            >
              {avatarLoading ? 'מעלה...' : user?.avatar_url ? 'החלף תמונה' : 'העלאת תמונה'}
            </Button>
            {avatarError && (
              <Typography variant="caption" color="error">
                {avatarError}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary">
              JPG, PNG, GIF או WEBP עד {MAX_MB}MB
            </Typography>
          </Box>

          <TextField
            fullWidth
            label="שם פרטי"
            value={formData.first_name || ''}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, first_name: v });
              const err = validateFirstNameLive(v);
              setErrors((prev) => (err ? { ...prev, first_name: err } : (() => { const n = { ...prev }; delete n.first_name; return n; })()));
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateFirstNameLive(formData.first_name || '');
              setErrors((prev) => (err ? { ...prev, first_name: err } : (() => { const n = { ...prev }; delete n.first_name; return n; })()));
            }}
            error={!!errors.first_name}
            helperText={errors.first_name}
            sx={{ mb: 2 }}
          />

          <TextField
            fullWidth
            label="שם משפחה"
            value={formData.last_name || ''}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, last_name: v });
              const err = validateLastNameLive(v);
              setErrors((prev) => (err ? { ...prev, last_name: err } : (() => { const n = { ...prev }; delete n.last_name; return n; })()));
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateLastNameLive(formData.last_name || '');
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
            value={formData.email || ''}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, email: v });
              const err = validateEmailLive(v);
              setErrors((prev) => (err ? { ...prev, email: err } : (() => { const n = { ...prev }; delete n.email; return n; })()));
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateEmailLive(formData.email || '');
              setErrors((prev) => (err ? { ...prev, email: err } : (() => { const n = { ...prev }; delete n.email; return n; })()));
            }}
            error={!!errors.email}
            helperText={errors.email}
            sx={{ mb: 2 }}
          />

          <TextField
            fullWidth
            label="מספר טלפון"
            value={formData.phone || ''}
            onChange={(e) => {
              const v = e.target.value;
              setFormData({ ...formData, phone: v });
              const err = validatePhoneLive(v);
              setErrors((prev) => (err ? { ...prev, phone: err } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
              setFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validatePhoneLive(formData.phone || '');
              setErrors((prev) => (err ? { ...prev, phone: err } : (() => { const n = { ...prev }; delete n.phone; return n; })()));
            }}
            error={!!errors.phone}
            helperText={errors.phone || 'לדוגמה: 050-1234567'}
            sx={{ mb: 3 }}
          />

          <Button
            type="submit"
            variant="contained"
            disabled={loading}
            fullWidth
          >
            שמור שינויים
          </Button>
        </form>
      </Paper>

      {/* Change Password */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          שינוי סיסמה
        </Typography>
        <Divider sx={{ my: 2 }} />

        <form onSubmit={handlePasswordSubmit} noValidate>
          <FormErrors errors={passwordFormErrors} title="שגיאות בשינוי סיסמה" />
          <PasswordField
            label="סיסמה נוכחית"
            value={passwordData.current_password}
            onChange={(v) => {
              setPasswordData({ ...passwordData, current_password: v });
              setPasswordErrors((prev) => { const n = { ...prev }; delete n.current_password; return n; });
              setPasswordFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              if (!passwordData.current_password) {
                setPasswordErrors((prev) => ({ ...prev, current_password: 'סיסמה נוכחית היא שדה חובה' }));
              }
            }}
            required
            error={!!passwordErrors.current_password}
            helperText={passwordErrors.current_password}
            sx={{ mb: 2 }}
          />
          <PasswordField
            label="סיסמה חדשה"
            value={passwordData.new_password}
            onChange={(v) => {
              setPasswordData({ ...passwordData, new_password: v });
              const err = validatePasswordLive(v);
              setPasswordErrors((prev) => (err ? { ...prev, new_password: err } : (() => { const n = { ...prev }; delete n.new_password; return n; })()));
              // Also validate confirm password if it has a value
              if (passwordData.confirm_password) {
                const confirmErr = validateConfirmPasswordLive(passwordData.confirm_password, v);
                setPasswordErrors((prev) => (confirmErr ? { ...prev, confirm_password: confirmErr } : (() => { const n = { ...prev }; delete n.confirm_password; return n; })()));
              }
              setPasswordFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validatePasswordLive(passwordData.new_password);
              setPasswordErrors((prev) => (err ? { ...prev, new_password: err } : (() => { const n = { ...prev }; delete n.new_password; return n; })()));
            }}
            required
            error={!!passwordErrors.new_password}
            helperText={passwordErrors.new_password || 'מינימום 8 תווים, ספרה ואות'}
            sx={{ mb: 2 }}
          />
          <PasswordField
            label="אימות סיסמה חדשה"
            value={passwordData.confirm_password || ''}
            onChange={(v) => {
              setPasswordData({ ...passwordData, confirm_password: v });
              const err = validateConfirmPasswordLive(v, passwordData.new_password);
              setPasswordErrors((prev) => (err ? { ...prev, confirm_password: err } : (() => { const n = { ...prev }; delete n.confirm_password; return n; })()));
              setPasswordFormErrors((prev) => (prev.length ? [] : prev));
            }}
            onBlur={() => {
              const err = validateConfirmPasswordLive(passwordData.confirm_password || '', passwordData.new_password);
              setPasswordErrors((prev) => (err ? { ...prev, confirm_password: err } : (() => { const n = { ...prev }; delete n.confirm_password; return n; })()));
            }}
            required
            error={!!passwordErrors.confirm_password}
            helperText={passwordErrors.confirm_password}
            sx={{ mb: 3 }}
          />

          <Button
            type="submit"
            variant="contained"
            color="secondary"
            disabled={passwordLoading}
            fullWidth
          >
            שנה סיסמה
          </Button>
        </form>
      </Paper>
    </Container>
  );
};

export default ProfileEditPage;
