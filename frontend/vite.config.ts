import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { sentryVitePlugin } from '@sentry/vite-plugin'

// Source maps for Sentry, only in a production image build that was given the token (see
// frontend/Dockerfile and docker-compose.prod.yml). They are "hidden" (no sourceMappingURL comment)
// and deleted from dist/ after upload, so the public site never serves them. Without the token
// nothing changes: no maps, no plugin, no network call.
const sentryUpload = Boolean(
  process.env.SENTRY_AUTH_TOKEN && process.env.SENTRY_ORG && process.env.SENTRY_PROJECT,
)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    ...(sentryUpload
      ? [
          sentryVitePlugin({
            org: process.env.SENTRY_ORG,
            project: process.env.SENTRY_PROJECT,
            authToken: process.env.SENTRY_AUTH_TOKEN,
            // EU-region orgs: leave unset when the token names its region; else https://de.sentry.io/
            url: process.env.SENTRY_URL || undefined,
            release: { name: process.env.VITE_SENTRY_RELEASE || undefined },
            sourcemaps: { filesToDeleteAfterUpload: ['./dist/**/*.map'] },
            telemetry: false,
          }),
        ]
      : []),
  ],
  build: { sourcemap: sentryUpload ? 'hidden' : false },
  // The backend's CORS allowlist names :5173. If the port is taken, fail loudly
  // instead of moving to :5174, where every API call would be blocked by CORS.
  server: { port: 5173, strictPort: true },
})
