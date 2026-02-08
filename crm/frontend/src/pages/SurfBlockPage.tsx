/**
 * Admin-only page: open from surf widget to create a block rule for the given URL.
 * Query: url=... (full URL or domain). Calls createGlobalRule with action=block.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, CircularProgress } from '@mui/material';
import { adminApi } from '../api/admin';

const SurfBlockPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const url = searchParams.get('url')?.trim();
    if (!url) {
      setStatus('error');
      setMessage('חסר פרמטר url');
      return;
    }
    const fullUrl = url.includes('://') ? url : `https://${url}`;
    adminApi
      .createGlobalRule({
        url: fullUrl,
        action: 'block',
        include_subdomains: true,
      })
      .then(() => {
        setStatus('ok');
        setMessage('האתר נחסם בהצלחה.');
      })
      .catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
        setStatus('error');
        setMessage(err?.response?.data?.detail || err?.message || 'שגיאה בחסימת האתר');
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

export default SurfBlockPage;
