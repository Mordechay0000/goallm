/**
 * First-time setup: when there are no users, show a dedicated screen
 * for registering the first user as admin. After that, admin registration is no longer possible.
 */
import React, { useEffect, useState } from 'react';
import { Container, Paper, Typography, Box, CircularProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import RegisterWizard from './RegisterWizard';

const setupMode = {
  title: 'הרשמת מנהל מערכת',
  subtitle:
    'זו הפעם הראשונה שהמערכת מופעלת. המשתמש שיירשם כאן יוגדר אוטומטית כמנהל. לאחר מכן לא ניתן להירשם כמנהל – רק מנהלים יוכלו להוסיף משתמשים.',
  successMessage:
    'מנהל המערכת נוצר. התחבר עם הטלפון והסיסמה שבחרת.',
};

const SetupPage: React.FC = () => {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);

  useEffect(() => {
    let cancelled = false;
    authApi
      .getSetupStatus()
      .then((res) => {
        if (!cancelled) {
          setNeedsSetup(res.needs_setup);
          if (!res.needs_setup) {
            navigate('/login', { replace: true });
          }
        }
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { replace: true });
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  if (checking) {
    return (
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'background.default',
        }}
      >
        <CircularProgress sx={{ color: 'primary.main' }} />
      </Box>
    );
  }

  if (!needsSetup) {
    return null;
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundColor: 'background.default',
        pt: 2,
        pb: 4,
      }}
    >
      <Container maxWidth="md">
        <Paper
          elevation={0}
          className="brand-gradient-subtle"
          sx={{
            p: 4,
            mb: 3,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 3,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <Typography
            component="h1"
            variant="h4"
            sx={{
              fontWeight: 700,
              color: 'primary.main',
              mb: 1,
              textAlign: 'center',
            }}
          >
            התקנת המערכת
          </Typography>
          <Typography
            variant="body1"
            color="text.secondary"
            sx={{ textAlign: 'center', maxWidth: 480, mx: 'auto' }}
          >
            {setupMode.subtitle}
          </Typography>
        </Paper>
        <RegisterWizard setupMode={setupMode} />
      </Container>
    </Box>
  );
};

export default SetupPage;
