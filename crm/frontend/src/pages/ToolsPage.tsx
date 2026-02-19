/**
 * דף כלים – אוסף כלים למשתמש (הקלטת תעבורה ועוד).
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Card,
  CardActionArea,
  CardContent,
  Grid,
} from '@mui/material';
import {
  Traffic as TrafficIcon,
  Build as BuildIcon,
} from '@mui/icons-material';

const tools = [
  {
    id: 'traffic',
    title: 'הקלטת תעבורה',
    description: 'צפייה בכתובות שגלשת אליהן עם מצב (פתוח, חסום, חוסר בתעודת אבטחה ועוד)',
    path: '/tools/traffic',
    icon: <TrafficIcon color="primary" sx={{ fontSize: 40 }} />,
  },
];

const ToolsPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          כלים
        </Typography>
        <Typography variant="body2" color="text.secondary">
          כלים שימושיים לניהול הגלישה וההגדרות
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {tools.map((tool) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={tool.id}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardActionArea
                onClick={() => navigate(tool.path)}
                sx={{ height: '100%', display: 'block', textAlign: 'right' }}
              >
                <CardContent sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
                  <Box sx={{ color: 'primary.main' }}>{tool.icon}</Box>
                  <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
                    {tool.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {tool.description}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>

      {tools.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <BuildIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
          <Typography color="text.secondary">אין כלים זמינים כרגע</Typography>
        </Paper>
      )}
    </Container>
  );
};

export default ToolsPage;
