// Government / Health-Authority dashboard entry point.
//
// The planning doc requires a dedicated portal for health officials
// ("சுகாதாரத்துறைக்கு தனியா ஒரு Web App அல்லது Dashboard") — the Community
// Health Intelligence dashboard IS that surface. It lives at
// /doctor/analytics for clinicians; this route exposes the identical
// component at a role-neutral URL for HOSPITAL/ADMIN (health-authority)
// accounts, without duplicating any logic.
export { default } from '../doctor/analytics/page';
