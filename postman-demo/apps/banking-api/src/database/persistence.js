/**
 * Persistent banking database backed by SQLite (node:sqlite, zero external deps).
 *
 * Each demo run's full state is stored as a canonical JSON snapshot in the
 * `bank_runs` table. The default run is hydrated on boot so accounts,
 * transactions, balances and beneficiaries survive restarts.
 */

const { DatabaseSync } = require('node:sqlite');
const fs = require('fs');
const path = require('path');

const DISABLED = process.env.BANK_PERSISTENCE === '0' || process.env.NODE_ENV === 'test';
const DB_PATH = process.env.BANK_DB_PATH || path.join(__dirname, '..', '..', 'data', 'bank.db');

let insertStmt;
let selectStmt;
let deleteStmt;

if (!DISABLED) {
  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
  const sqlite = new DatabaseSync(DB_PATH);
  sqlite.exec(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS bank_runs (
      run_id       TEXT PRIMARY KEY,
      seed_version TEXT NOT NULL,
      state_json   TEXT NOT NULL,
      updated_at   TEXT NOT NULL
    );
  `);
  insertStmt = sqlite.prepare(
    'INSERT INTO bank_runs (run_id, seed_version, state_json, updated_at) VALUES (?, ?, ?, ?) ' +
    'ON CONFLICT(run_id) DO UPDATE SET seed_version = excluded.seed_version, state_json = excluded.state_json, updated_at = excluded.updated_at'
  );
  selectStmt = sqlite.prepare('SELECT state_json FROM bank_runs WHERE run_id = ?');
  deleteStmt = sqlite.prepare('DELETE FROM bank_runs WHERE run_id = ?');
}

const mapEntries = map => Array.from(map.entries());

function serializeState(state) {
  return {
    accounts: mapEntries(state.accounts).map(([id, value]) => [id, { ...value }]),
    transactions: mapEntries(state.transactions).map(([id, value]) => [id, { ...value }]),
    disputes: mapEntries(state.disputes).map(([id, value]) => [id, {
      ...value,
      evidence: (value.evidence || []).map(item => ({ ...item }))
    }]),
    customers: mapEntries(state.customers),
    beneficiaries: mapEntries(state.beneficiaries),
    cards: mapEntries(state.cards),
    scheduledPayments: mapEntries(state.scheduledPayments),
    standingOrders: mapEntries(state.standingOrders),
    directDebits: mapEntries(state.directDebits),
    notificationPreferences: mapEntries(state.notificationPreferences),
    auditEvents: state.auditEvents.map(value => ({ ...value })),
    principals: mapEntries(state.principals),
    credentials: mapEntries(state.credentials),
    idempotency: mapEntries(state.idempotency),
    metadata: {
      counters: { ...state.metadata.counters },
      clock: state.metadata.clock
    }
  };
}

function saveRun(runId, seedVersion, state) {
  if (DISABLED) return;
  insertStmt.run(runId, String(seedVersion), JSON.stringify(serializeState(state)), new Date().toISOString());
}

function loadRun(runId) {
  if (DISABLED) return null;
  const row = selectStmt.get(runId);
  if (!row) return null;
  try {
    return JSON.parse(row.state_json);
  } catch {
    return null;
  }
}

function deleteRun(runId) {
  if (DISABLED) return;
  deleteStmt.run(runId);
}

module.exports = { saveRun, loadRun, deleteRun, DB_PATH, DISABLED };
