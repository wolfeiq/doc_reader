# Production Readiness Checklist 

## What Should be Ideally Implemented for a Fully Production Ready App

### Security
- [ ] **Authentication & authorization**
  - No user authentication system currently
  - Add JWT/OAuth for API endpoints
  - Protect admin routes (document upload, delete operations)

- [ ] **Set up CORS properly**
  - Current: Hardcoded localhost urls -> these should go to the .env files before prod (TODO)

- [ ] **Database credentials**
  - Credentials for the database should be changed, new OpenAI API key created (TODO)

- [ ] **Add rate limiting**
  - Use Redis for rate limiting & with db User ID and timestamps

### Configuration

- [ ] **Environment-specific configs**
  - Hardcoded configs must be removed again (TODO)

### Infrastructure

- [ ] **Implement graceful shutdown**
  - Close database connections cleanly
  - Finish in-flight Celery tasks

- [ ] **Frontend error boundaries**
  - Add React error boundaries for all major components
  - Display user-friendly error messages
  - Log errors to monitoring service
  - Rate Limiting toast messages shown to users with Redis

### Monitoring & Logging

- [ ] **Structured logging**
  - Replace print statements with proper logging (TODO)
  - Use JSON format for log aggregation
  - Sentry for error tracking

### Database

- [ ] **Database migrations**
  - Set up Alembic for schema migrations
  - Create initial migration from current models
  - Document migration process

- [ ] **Database backups**
  - Automated daily backups
  - Test restore procedures
  - Set up point-in-time recovery

### Performance

- [ ] **Add caching layer**
  - Cache frequent database queries in Redis
  - Cache ChromaDB search results (with TTL)
  - Cache document section content

- [ ] **Optimize ChromaDB**
  - Review embedding batch sizes
  - Add persistent storage volume
  - Consider using a managed vector DB for production

- [ ] **Frontend optimization**
  - [ ] Add bundle analysis (check bundle size)
  - [ ] Implement code splitting
  - [ ] Optimize images and assets (currently none, but if images were to be added)
  - [ ] Improved TypeSafety
 

## ToDos

### Testing
- [ ] **Backend tests**
  - Unit tests for services (TODO)
  - Integration tests for API endpoints (TODO)
  - (E2E tests for critical flows)
  - Target: >80% coverage

- [ ] **Frontend tests**
  - Component tests with React Testing Library (TODO)
  - Effect Library for error handling
  - E2E tests with Playwright/Cypress
  - Visual regression tests

### DevOps
- [ ] **CI/CD pipeline**
  - Automated testing on PR
  - Automated deployment to staging
  - Manual approval for production
  - Rollback capabilities