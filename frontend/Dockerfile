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
    CMD wget -q --spider http://localhost:8080/index.html || exit 1
