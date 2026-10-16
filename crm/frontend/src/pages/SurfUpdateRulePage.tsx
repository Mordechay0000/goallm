/**
 * Admin-only page: open from surf widget to update the existing rule (by domain+path) to block.
 * Query: rule_domain=...&rule_path=... Acts only after an explicit click.
 */
import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, CircularProgress, Button } from '@mui/material';
import { adminApi } from '../api/admin';

const SurfUpdateRulePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const ruleDomain = searchParams.get('rule_domain')?.trim() || '';
  const rulePath = searchParams.get('rule_path')?.trim() || '/';

  const apply = async () => {
    if (!ruleDomain) {
      setStatus('error');
      setMessage('חסר פרמטר rule_domain');
      return;
    }
    setStatus('loading');
    try {
      await adminApi.surfUpdateRuleToBlock(ruleDomain, rulePath);
      setStatus('ok');
      setMessage('הכלל עודכן לחסום בהצלחה.');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setStatus('error');
      setMessage(ax?.response?.data?.detail || ax?.message || 'שגיאה בעדכון הכלל');
    }
  };

  return (
    <Box sx={{ p: 3, textAlign: 'center' }}>
      {status === 'idle' && (
        <>
          <Typography sx={{ mb: 2, wordBreak: 'break-all' }}>
            לעדכן לחסימה את הכלל: {ruleDomain || '—'}
            {rulePath !== '/' ? rulePath : ''}
          </Typography>
          <Button variant="contained" color="error" onClick={apply}>
            אשר עדכון לחסימה
          </Button>
        </>
      )}
      {status === 'loading' && <CircularProgress />}
      {status === 'ok' && <Typography color="success.main">{message}</Typography>}
      {status === 'error' && <Typography color="error">{message}</Typography>}
    </Box>
  );
};

export default SurfUpdateRulePage;
