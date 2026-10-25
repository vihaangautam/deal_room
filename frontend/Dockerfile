# Build the SPA, then serve the static output with nginx.
#
# VITE_API_URL is baked into the bundle at build time, not read at
# runtime — so it is a build arg, not an environment variable on the
# running container. Setting it after the image is built does nothing.

FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Same-origin under the /api prefix that nginx strips (see nginx.conf).
# The prefix is not decoration: the API mounts at the root and its paths
# collide with the SPA's routes, so /deals would otherwise be ambiguous.
# Override only if the API is served from a different origin, and expect
# to revisit CORS and the cookie's SameSite if you do.
ARG VITE_API_URL="/api"
ENV VITE_API_URL=$VITE_API_URL

# vite.config.ts sets envDir to the repo root, so a .env there would
# override this. The build context is frontend/ only, so there is no
# repo-root .env in the image and the arg above is what lands.
RUN npm run build


FROM nginx:1.27-alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    # 127.0.0.1, not localhost. nginx's `listen 8080;` binds IPv4 only,
    # while wget resolves localhost to ::1 first and gets "connection
    # refused" — so the container reported unhealthy from the moment it
    # started while serving every request perfectly. A health signal that
    # is always red tells you nothing when something is actually wrong,
    # and anything waiting on service_healthy would wait forever.
    CMD wget -q --spider http://127.0.0.1:8080/index.html || exit 1
