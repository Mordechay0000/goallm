/**
 * Admin: human review queue.
 * - Images the model was unsure about (P(Yes) in the uncertain band) – they stay hidden until decided here.
 * - Images whose automatic analysis kept failing (they stay blocked meanwhile).
 * - Videos: per-video review results; uncertain ones wait here; any decision can be overridden.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardActions, CardContent, CardMedia, Chip, Grid, Link, Paper, Stack, Tab, Tabs, Typography,
} from '@mui/material';
import { reviewQueueApi, VIDEO_STATUS_LABELS, type ReviewImage, type VideoReview } from '../api/review';

const FLAG_LABELS: Record<string, string> = {
  female_visible_9_plus: 'אישה/ילדה 9+',
  female_3_to_9_partial_clothing: 'ילדה 3–9 לבוש חלקי',
  female_under_3_minimal_clothing: 'תינוקת לא לבושה',
  boys_teens_men_exposed_or_bathing: 'גבר/נער חשוף',
  any_visible_body_exposure: 'חשיפה',
};

const Thumb: React.FC<{ load: () => Promise<string> }> = ({ load }) => {
  const [src, setSrc] = useState<string>('');
  useEffect(() => {
    let alive = true;
    let objectUrl = '';
    load()
      .then((u) => {
        objectUrl = u;
        if (alive) setSrc(u);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [load]);
  return src ? (
    <CardMedia component="img" image={src} sx={{ height: 200, objectFit: 'contain', bgcolor: '#f4f4f4' }} />
  ) : (
    <Box sx={{ height: 200, bgcolor: '#f4f4f4', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Typography variant="caption">אין תמונה שמורה</Typography>
    </Box>
  );
};

const ImagesTab: React.FC<{ status: 'review' | 'error' }> = ({ status }) => {
  const [items, setItems] = useState<ReviewImage[]>([]);
  const [error, setError] = useState('');
  const load = useCallback(() => {
    reviewQueueApi.images(status).then(setItems).catch(() => setError('טעינה נכשלה'));
  }, [status]);
  useEffect(() => {
    const t = setTimeout(load, 0);
    return () => clearTimeout(t);
  }, [load]);
  const decide = async (hash: string, decision: 'allow' | 'block') => {
    await reviewQueueApi.decideImage(hash, decision);
    setItems((prev) => prev.filter((i) => i.image_hash !== hash));
  };
  return (
    <>
      {error && <Alert severity="error">{error}</Alert>}
      {items.length === 0 && <Typography sx={{ p: 2 }}>אין תמונות בתור.</Typography>}
      <Grid container spacing={2}>
        {items.map((img) => (
          <Grid key={img.image_hash} size={{ xs: 12, sm: 6, md: 4 }}>
            <Card>
              {img.has_thumb ? (
                <Thumb load={() => reviewQueueApi.imageThumb(img.image_hash)} />
              ) : (
                <Thumb load={() => Promise.reject(new Error('none'))} />
              )}
              <CardContent>
                <Typography variant="caption" sx={{ wordBreak: 'break-all', direction: 'ltr', display: 'block' }}>
                  {img.image_url || img.image_hash}
                </Typography>
                <Stack direction="row" spacing={0.5} sx={{ mt: 1, flexWrap: 'wrap' }}>
                  {Object.keys(img.flags).map((f) => (
                    <Chip key={f} size="small" label={FLAG_LABELS[f] || f} />
                  ))}
                  {status === 'error' && <Chip size="small" color="warning" label={`${img.attempts} ניסיונות`} />}
                </Stack>
              </CardContent>
              <CardActions>
                <Button color="success" onClick={() => decide(img.image_hash, 'allow')}>אשר</Button>
                <Button color="error" onClick={() => decide(img.image_hash, 'block')}>חסום</Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </>
  );
};

const VideosTab: React.FC = () => {
  const [items, setItems] = useState<VideoReview[]>([]);
  const load = useCallback(() => {
    reviewQueueApi.videos().then(setItems).catch(() => setItems([]));
  }, []);
  useEffect(() => {
    const t = setTimeout(load, 0);
    const timer = setInterval(load, 10000);
    return () => {
      clearTimeout(t);
      clearInterval(timer);
    };
  }, [load]);
  const decide = async (key: string, decision: 'allow' | 'block' | 'requeue') => {
    const updated = await reviewQueueApi.decideVideo(key, decision);
    setItems((prev) => prev.map((v) => (v.video_key === key ? { ...v, ...updated } : v)));
  };
  return (
    <Stack spacing={2}>
      {items.length === 0 && <Typography sx={{ p: 2 }}>אין סרטונים.</Typography>}
      {items.map((v) => (
        <Paper key={v.video_key} sx={{ p: 2 }}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <Box sx={{ width: { md: 260 } }}>
              {v.has_thumb && v.video_key ? (
                <Card><Thumb load={() => reviewQueueApi.videoThumb(v.video_key as string)} /></Card>
              ) : null}
            </Box>
            <Box sx={{ flex: 1 }}>
              {/^https?:\/\//.test(v.source_url || '') ? (
                <Link href={v.source_url} target="_blank" rel="noopener noreferrer" sx={{ wordBreak: 'break-all', direction: 'ltr', textAlign: 'left', display: 'block' }}>
                  {v.source_url}
                </Link>
              ) : (
                <Typography sx={{ wordBreak: 'break-all', direction: 'ltr', textAlign: 'left' }}>{v.source_url}</Typography>
              )}
              <Stack direction="row" spacing={1} sx={{ my: 1, flexWrap: 'wrap' }}>
                <Chip label={VIDEO_STATUS_LABELS[v.status || ''] || v.status} />
                {v.duration_sec != null && <Chip size="small" label={`${Math.round(v.duration_sec)} שניות`} />}
                {v.frames_sampled != null && (
                  <Chip size="small" label={`נבדקו ${v.frames_analyzed ?? 0} מתוך ${v.frames_sampled} פריימים`} />
                )}
                {v.blocked_at_sec != null && <Chip size="small" color="warning" label={`בשנייה ${Math.round(v.blocked_at_sec)}`} />}
              </Stack>
              {v.reason && <Typography variant="body2" color="text.secondary">{v.reason}</Typography>}
              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Button size="small" color="success" onClick={() => decide(v.video_key as string, 'allow')}>אשר לכולם</Button>
                <Button size="small" color="error" onClick={() => decide(v.video_key as string, 'block')}>חסום</Button>
                <Button size="small" onClick={() => decide(v.video_key as string, 'requeue')}>בדיקה אוטומטית מחדש</Button>
              </Stack>
            </Box>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
};

const AdminReviewPage: React.FC = () => {
  const [tab, setTab] = useState(0);
  return (
    <Box sx={{ p: { xs: 2, sm: 3 } }}>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>תור בדיקה אנושית</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        תמונות שהמודל לא היה בטוח בהן לא מוצגות לגולשים עד להחלטה כאן. תמונות שהניתוח שלהן נכשל שוב ושוב נשארות חסומות.
      </Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="תמונות – המודל לא בטוח" />
        <Tab label="תמונות – ניתוח נכשל" />
        <Tab label="סרטונים" />
      </Tabs>
      {tab === 0 && <ImagesTab status="review" />}
      {tab === 1 && <ImagesTab status="error" />}
      {tab === 2 && <VideosTab />}
    </Box>
  );
};

export default AdminReviewPage;
