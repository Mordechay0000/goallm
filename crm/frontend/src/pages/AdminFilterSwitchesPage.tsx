/**
 * Admin: global filter switches. Enable/disable each filter type independently. Admin only.
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Container,
  Paper,
  Typography,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Stack,
} from '@mui/material';
import { adminApi, type FilterSwitches } from '../api/admin';

const FILTER_LABELS: Record<keyof FilterSwitches, string> = {
  url_policy: 'סינון כתובת (URL) – חסימת/אפשרות דפים וכתובות לפי רשימה',
  text_filter: 'סינון טקסט – סינון תוכן טקסט בדפי HTML',
  image_filter: 'סינון תמונות – החלפת תמונות (כתובת ישירה) לפי ניתוח',
  embedded_image_filter: 'סינון תמונות מוטמעות – תמונות data: בתוך HTML',
  file_download_filter: 'סינון הורדות קבצים – שליחה לבדיקה עם תיאור הקובץ',
};

const DEFAULT_SWITCHES: FilterSwitches = {
  url_policy: true,
  text_filter: true,
  image_filter: true,
  embedded_image_filter: true,
  file_download_filter: true,
};

const AdminFilterSwitchesPage: React.FC = () => {
  const [switches, setSwitches] = useState<FilterSwitches>({ ...DEFAULT_SWITCHES });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getFilterSwitches();
      setSwitches({ ...DEFAULT_SWITCHES, ...data });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'שגיאה בטעינת המתגים');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggle = async (key: keyof FilterSwitches, value: boolean) => {
    const next = { ...switches, [key]: value };
    setSwitches(next);
    setSaving(true);
    setError(null);
    try {
      const updated = await adminApi.updateFilterSwitches({ [key]: value });
      setSwitches({ ...DEFAULT_SWITCHES, ...updated });
    } catch (e) {
      setSwitches(switches);
      setError(e instanceof Error ? e.message : 'שגיאה בעדכון');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          מתגי סינון גלובליים
        </Typography>
        <Typography variant="body2" color="text.secondary">
          כל סינון פועל באופן עצמאי. כיבוי סינון אחד לא משפיע על השאר.
        </Typography>
      </Box>
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Paper sx={{ p: 3 }}>
        <Box className="card-header-accent" sx={{ mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>הפעלת סינונים</Typography>
        </Box>
        <Stack spacing={2}>
          {(Object.keys(FILTER_LABELS) as (keyof FilterSwitches)[]).map((key) => (
            <Box
              key={key}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 2,
                py: 1,
                borderBottom: '1px solid',
                borderColor: 'divider',
                '&:last-of-type': { borderBottom: 'none' },
              }}
            >
              <FormControlLabel
                control={
                  <Switch
                    checked={!!switches[key]}
                    onChange={(_, checked) => handleToggle(key, checked)}
                    disabled={saving}
                    color="primary"
                  />
                }
                label={
                  <Typography variant="body1" component="span">
                    {FILTER_LABELS[key]}
                  </Typography>
                }
                labelPlacement="start"
                sx={{ ml: 0, flex: 1 }}
              />
              <Typography variant="caption" color="text.secondary">
                {switches[key] ? 'מופעל' : 'כבוי'}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Paper>
    </Container>
  );
};

export default AdminFilterSwitchesPage;
