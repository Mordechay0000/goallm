/**
 * שיוך מכשיר (IP) לחשבון – שלב אחר שלב.
 * מגיעים לכאן כשגולשים דרך הסינון ו־IP לא משויך. אחרי התחברות + שיוך אפשר לחזור לגלוש.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Button,
  Box,
  Stepper,
  Step,
  StepLabel,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useAuthStore } from '../store/authStore';
import { bindingsApi } from '../api/bindings';
import { Login as LoginIcon, PersonAdd as PersonAddIcon, Link as LinkIcon, CheckCircle as CheckCircleIcon } from '@mui/icons-material';

const BindPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const returnUrl = searchParams.get('return_url') || '/';
  const fromLogin = searchParams.get('from_login') === '1';
  const { isAuthenticated } = useAuthStore();
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [clientIp, setClientIp] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [bindingError, setBindingError] = useState<string>('');

  // Force re-login on bind: show step 0 until user explicitly went through login/register and returned with from_login=1. Even if already logged in, we never skip to step 1 without from_login.
  useEffect(() => {
    if (step === 2) return; // keep success step
    if (!fromLogin) {
      setStep(0);
      return;
    }
    if (isAuthenticated) {
      setStep(1);
      setBindingError('');
      bindingsApi
        .getClientIp()
        .then((res) => setClientIp(res.ip || ''))
        .catch(() => setClientIp(''));
    } else {
      setStep(0);
    }
  }, [isAuthenticated, fromLogin, step]);

  const handleBind = async () => {
    setLoading(true);
    setBindingError('');
    try {
      await bindingsApi.bindCurrentIp();
      setStep(2);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err instanceof Error ? err.message : 'שיוך נכשל');
      setBindingError(String(msg));
    } finally {
      setLoading(false);
    }
  };

  const steps = ['כניסה לחשבון', 'חיבור המכשיר אליך', 'מוכן'];

  return (
    <Container maxWidth="sm" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" align="center" gutterBottom sx={{ fontWeight: 600 }}>
          חיבור המכשיר אל החשבון שלך
        </Typography>
        <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
          כדי שהגלישה מהמכשיר הזה תעבוד עם ההגדרות שלך, צריך לחבר אותו לחשבון. שני שלבים קצרים.
        </Typography>

        <Stepper activeStep={step} alternativeLabel sx={{ mb: 3 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* שלב 0: בחירה – כבר יש חשבון או רוצה ליצור */}
        {step === 0 && (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography variant="body1" paragraph>
              איך תרצה להמשיך?
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'stretch', maxWidth: 320, mx: 'auto', mt: 2 }}>
              <Button
                variant="contained"
                component={Link}
                to={`/login?redirect=${encodeURIComponent('/bind' + (returnUrl && returnUrl !== '/' ? '?return_url=' + encodeURIComponent(returnUrl) + '&from_login=1' : '?from_login=1'))}`}
                startIcon={<LoginIcon />}
                size="large"
                fullWidth
              >
                כבר יש לי חשבון – אני רוצה להיכנס
              </Button>
              <Button
                variant="outlined"
                component={Link}
                to={returnUrl && returnUrl !== '/' ? `/register?redirect=${encodeURIComponent('/bind?return_url=' + encodeURIComponent(returnUrl) + '&from_login=1')}` : '/register'}
                startIcon={<PersonAddIcon />}
                size="large"
                fullWidth
              >
                אין לי עדיין חשבון – אני רוצה ליצור אחד
              </Button>
            </Box>
          </Box>
        )}

        {/* שלב 1: מחובר – הצג IP ולחצן שיוך */}
        {step === 1 && (
          <Box sx={{ py: 2 }}>
            <Typography variant="body1" paragraph>
              זה המספר שמזהה את המכשיר שלך אצלנו (כתובת IP):
            </Typography>
            <Paper variant="outlined" sx={{ p: 2, mb: 2, textAlign: 'center' }}>
              <Typography variant="h6" component="code" sx={{ fontFamily: 'monospace' }}>
                {clientIp || '...'}
              </Typography>
            </Paper>
            <Typography variant="body2" color="text.secondary" paragraph>
              לוחצים על הכפתור למטה ומקשרים את המכשיר לחשבון. אחרי זה הגלישה תעבוד עם ההגדרות שבחרת.
            </Typography>
            {bindingError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {bindingError}
              </Alert>
            )}
            <Button
              variant="contained"
              fullWidth
              onClick={handleBind}
              disabled={loading || !clientIp}
              startIcon={loading ? <CircularProgress size={20} /> : <LinkIcon />}
              size="large"
            >
              {loading ? 'מקשר...' : 'כן, לקשר את המכשיר הזה לחשבון שלי'}
            </Button>
          </Box>
        )}

        {/* שלב 2: הושלם */}
        {step === 2 && (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <CheckCircleIcon color="success" sx={{ fontSize: 56, mb: 1 }} />
            <Typography variant="h6" paragraph>
              המכשיר מחובר לחשבון שלך
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              מעכשיו כשתגלוש מהמכשיר הזה, ההגדרות שלך יחולו אוטומטית. כל שינוי שתעשה כאן יישמר ויעבוד מיד.
            </Typography>
            <Button
              variant="contained"
              size="large"
              onClick={() => (window.location.href = returnUrl)}
              startIcon={<LinkIcon />}
            >
              חזרה לגלישה
            </Button>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default BindPage;
