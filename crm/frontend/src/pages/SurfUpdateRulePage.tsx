/**
 * Admin-only page: open from surf widget to update the existing rule (by domain+path) to block.
 * Query: rule_domain=...&rule_path=...
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, CircularProgress } from '@mui/material';
import { adminApi } from '../api/admin';

const SurfUpdateRulePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const ruleDomain = searchParams.get('rule_domain')?.trim();
    const rulePath = searchParams.get('rule_path')?.trim() || '/';
    if (!ruleDomain) {
      setStatus('error');
      setMessage('חסר פרמטר rule_domain');
      return;
    }
    adminApi
      .surfUpdateRuleToBlock(ruleDomain, rulePath)
      .then(() => {
        setStatus('ok');
        setMessage('הכלל עודכן לחסום בהצלחה.');
      })
      .catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
        setStatus('error');
        setMessage(err?.response?.data?.detail || err?.message || 'שגיאה בעדכון הכלל');
      });
  }, [searchParams]);

  return (
    <Box sx={{ p: 3, textAlign: 'center' }}>
      {status === 'loading' && <CircularProgress />}
      {status === 'ok' && <Typography color="success.main">{message}</Typography>}
      {status === 'error' && <Typography color="error">{message}</Typography>}
    </Box>
  );
};

export default SurfUpdateRulePage;
