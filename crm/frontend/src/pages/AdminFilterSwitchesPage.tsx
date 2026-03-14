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
  surf_widget: 'סרגל דיווח (ווידג׳ט) – דחיפת תגית דיווח ומנהל לדפים',
  pdf_filter_text: 'סינון טקסט ב-PDF – חילוץ טקסט מקובץ PDF וסינון לפי ניתוח',
  pdf_filter_images: 'סינון תמונות ב-PDF – החלפת תמונות בתוך PDF לפי ניתוח',
  file_share_block: 'שיתוף קבצים ציבורי – דף "שלח לבדיקה" לקישורים מאתרי שיתוף',
  google_search_filter: 'סינון תוצאות גוגל – הסתרת תוצאות חסומות/לא ידועות',
};

const DEFAULT_SWITCHES: FilterSwitches = {
  url_policy: true,
  text_filter: true,
  image_filter: true,
  embedded_image_filter: true,
  file_download_filter: true,
  surf_widget: true,
  pdf_filter_text: true,
  pdf_filter_images: true,
  file_share_block: true,
  google_search_filter: true,
};

/** Grouped sections for a tidy, intuitive layout */
const SECTIONS: { title: string; keys: (keyof FilterSwitches)[] }[] = [
  {
    title: 'מדיניות וכתובות',
    keys: ['url_policy'],
  },
  {
    title: 'סינון תוכן בדפים',
    keys: ['text_filter', 'image_filter', 'embedded_image_filter', 'google_search_filter'],
  },
  {
    title: 'קבצים ו-PDF',
    keys: ['file_download_filter', 'file_share_block', 'pdf_filter_text', 'pdf_filter_images'],
  },
  {
    title: 'אחר',
    keys: ['surf_widget'],
  },
];

function SwitchRow({
  switchKey,
  label,
  checked,
  saving,
  onToggle,
}: {
  switchKey: keyof FilterSwitches;
  label: string;
  checked: boolean;
  saving: boolean;
  onToggle: (key: keyof FilterSwitches, value: boolean) => void;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 2,
        py: 1.5,
        px: 0,
        borderBottom: '1px solid',
        borderColor: 'divider',
        '&:last-of-type': { borderBottom: 'none' },
      }}
    >
      <FormControlLabel
        control={
          <Switch
            checked={!!checked}
            onChange={(_, value) => onToggle(switchKey, value)}
            disabled={saving}
            color="primary"
          />
        }
        label={
          <Typography variant="body1" component="span">
            {label}
          </Typography>
        }
        labelPlacement="start"
        sx={{ ml: 0, flex: 1 }}
      />
      <Typography variant="caption" color="text.secondary">
        {checked ? 'מופעל' : 'כבוי'}
      </Typography>
    </Box>
  );
}

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
      <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
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

      <Stack spacing={3}>
        {SECTIONS.map((section) => (
          <Paper key={section.title} sx={{ p: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'text.secondary' }}>
              {section.title}
            </Typography>
            {section.title === 'קבצים ו-PDF' && (
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                כששני מתגי ה-PDF כבויים – קובץ ה-PDF לא יעובד ויועבר כמו שהוא.
              </Typography>
            )}
            <Stack spacing={0}>
              {section.keys.map((key) => (
                <SwitchRow
                  key={key}
                  switchKey={key}
                  label={FILTER_LABELS[key]}
                  checked={!!switches[key]}
                  saving={saving}
                  onToggle={handleToggle}
                />
              ))}
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Container>
  );
};

export default AdminFilterSwitchesPage;
