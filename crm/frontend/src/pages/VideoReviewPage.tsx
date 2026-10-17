/**
 * Send a video for review (opened from the surf widget). Like NetFree: the video is checked frame by frame
 * (1–2 frames per second, only frames where something changed go to the model) and, if clean, opened for everyone.
 * Query: url=<video url> (when the page exposes it) and/or page=<page url> (lists what the filter blocked there).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Container, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import { videoReviewApi, VIDEO_STATUS_LABELS, type BlockedMedia, type VideoReview } from '../api/review';

const statusColor = (s: VideoReview['status']) =>
  s === 'allowed' ? 'success' : s === 'blocked' ? 'error' : s === 'error' ? 'warning' : 'default';

const VideoReviewPage: React.FC = () => {
  const [params] = useSearchParams();
  const url = params.get('url') || '';
  const page = params.get('page') || '';
  const [review, setReview] = useState<VideoReview | null>(null);
  const [blocked, setBlocked] = useState<BlockedMedia[]>([]);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      if (url) setReview(await videoReviewApi.status(url));
      let items = await videoReviewApi.recentBlocked(page || null);
      if (!items.length && page) items = await videoReviewApi.recentBlocked(null);
      setBlocked(items);
    } catch {
      setError('לא הצלחנו לטעון את מצב הבדיקה');
    }
  }, [url, page]);

  useEffect(() => {
    // Initial load + polling while something is being reviewed (setState happens in the async callback).
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, 5000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh]);

  const send = async (mediaUrl: string) => {
    setError('');
    try {
      const r = await videoReviewApi.request(mediaUrl, page || null);
      if (mediaUrl === url) setReview(r);
      await refresh();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שליחה לבדיקה נכשלה');
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: 3, mb: 4 }}>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>
        בדיקת סרטון
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        הסרטון נבדק פריים אחרי פריים. סרטון שנמצא תקין נפתח לכל המשתמשים. שידור חי אינו ניתן לבדיקה מראש.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {url && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography sx={{ wordBreak: 'break-all', direction: 'ltr', textAlign: 'left', mb: 1 }}>{url}</Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            {review?.status ? (
              <Chip label={VIDEO_STATUS_LABELS[review.status] || review.status} color={statusColor(review.status)} />
            ) : (
              <Button variant="contained" onClick={() => send(url)}>שלח לבדיקה</Button>
            )}
            {review?.status === 'error' && <Button onClick={() => send(url)}>נסה שוב</Button>}
            {review?.reason && <Typography variant="body2" color="text.secondary">{review.reason}</Typography>}
          </Stack>
        </Paper>
      )}

      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        סרטונים שהסינון חסם לך לאחרונה{page ? ' בדף הזה' : ''}
      </Typography>
      <Paper>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>כתובת</TableCell>
              <TableCell>מצב</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {blocked.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3}>לא נמצאו סרטונים חסומים ב-24 השעות האחרונות.</TableCell>
              </TableRow>
            ) : (
              blocked.map((b) => (
                <TableRow key={b.media_key}>
                  <TableCell sx={{ wordBreak: 'break-all', direction: 'ltr', textAlign: 'left', maxWidth: 420 }}>{b.media_url}</TableCell>
                  <TableCell>
                    {b.review_status ? (
                      <Chip size="small" label={VIDEO_STATUS_LABELS[b.review_status] || b.review_status} color={statusColor(b.review_status)} />
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>
                    {(!b.review_status || b.review_status === 'error') && (
                      <Button size="small" variant="outlined" onClick={() => send(b.media_url)}>שלח לבדיקה</Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
      <Box sx={{ mt: 2 }}>
        <Typography variant="caption" color="text.secondary">
          אחרי שהסרטון אושר – רענן את הדף שבו הוא מופיע.
        </Typography>
      </Box>
    </Container>
  );
};

export default VideoReviewPage;
