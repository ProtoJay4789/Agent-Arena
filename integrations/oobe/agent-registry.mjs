#!/usr/bin/env node
/**
 * OOBE Protocol — Agent Identity for Agent Arena
 * 
 * Registers agents with PDA wallets, capabilities, pricing, reputation.
 * Standalone — no Solana SDK dependency (swap in when SDK is published).
 * 
 * Usage:
 *   node agent-registry.mjs          — full manifest
 *   node agent-registry.mjs --leaderboard — reputation board
 *   node agent-registry.mjs --agent ArenaTrader — single agent info
 */

// ─── Capability Schemas ────────────────────────────────────────────
const CAPABILITIES = {
  TRADING:     { name: 'Trading',        methods: ['swap','limit_order','dca','trailing_stop'], risk: 'medium' },
  VERIFICATION:{ name: 'Token Verify',   methods: ['scan','rug_check','risk_score'],            risk: 'low' },
  ANALYSIS:    { name: 'Market Analysis', methods: ['trend','risk_calc','recommendation'],       risk: 'low' },
  LP_MANAGEMENT:{ name: 'LP Manager',    methods: ['add_liq','remove_liq','rebalance'],         risk: 'high' },
  GOVERNANCE:  { name: 'Governance',      methods: ['analyze_proposal','vote','delegate'],       risk: 'medium' },
  ROASTING:    { name: 'Roast Engine',    methods: ['roast_topic','roast_battle','grade'],       risk: 'low' },
}

const PRICING = {
  FREE:       { tier: 'free',       costPerCall: 0,      dailyLimit: 100 },
  PREMIUM:    { tier: 'premium',    costPerCall: 0.001,  dailyLimit: 10000 },
  ENTERPRISE: { tier: 'enterprise', costPerCall: 0.0005, dailyLimit: 100000 },
}

// ─── Agent Definitions ─────────────────────────────────────────────
const AGENTS = [
  {
    name: 'ArenaTrader',
    description: 'Autonomous DeFi trader. Executes swaps, manages positions, follows signals.',
    capabilities: ['TRADING', 'ANALYSIS'],
    pricing: PRICING.PREMIUM,
    chain: 'solana',
  },
  {
    name: 'Rugcatcher',
    description: 'Token risk scanner. Detects rugs, honeypots, sketchy contracts.',
    capabilities: ['VERIFICATION', 'ANALYSIS'],
    pricing: PRICING.FREE,
    chain: 'solana',
  },
  {
    name: 'GovernanceBot',
    description: 'Multi-source governance intelligence. Recommends votes across protocols.',
    capabilities: ['GOVERNANCE', 'ANALYSIS'],
    pricing: PRICING.PREMIUM,
    chain: 'solana',
  },
  {
    name: 'LPManager',
    description: 'Liquidity pool optimizer. Manages positions, rebalances, collects fees.',
    capabilities: ['LP_MANAGEMENT', 'TRADING'],
    pricing: PRICING.ENTERPRISE,
    chain: 'solana',
  },
  {
    name: 'RoastMaster',
    description: 'Voice-powered roast engine. Rates tracks, roasts topics, educational content.',
    capabilities: ['ROASTING', 'ANALYSIS'],
    pricing: PRICING.FREE,
    chain: 'offchain',
  },
]

// ─── Registry Logic ────────────────────────────────────────────────
class AgentRegistry {
  constructor() {
    this.agents = new Map()
    for (const def of AGENTS) {
      this.agents.set(def.name, { ...def, reputation: 0, totalCalls: 0 })
    }
  }

  get(name) { return this.agents.get(name) }

  recordCall(name, success = true) {
    const a = this.agents.get(name)
    if (!a) return false
    a.totalCalls++
    a.reputation = success
      ? Math.min(100, a.reputation + 1)
      : Math.max(0, a.reputation - 2)
    return true
  }

  manifest() {
    return {
      protocol: 'OOBE Synapse SAP v2',
      programId: 'BoNnVobybZH3KkGXRvWNsEwCp3RbXXRpYbHSu6hZm6Y',
      chain: 'solana',
      agents: Array.from(this.agents.values()).map(a => ({
        name: a.name,
        description: a.description,
        capabilities: a.capabilities.map(c => ({
          schema: CAPABILITIES[c]?.name || c,
          methods: CAPABILITIES[c]?.methods || [],
          risk: CAPABILITIES[c]?.risk || 'unknown',
        })),
        pricing: a.pricing,
        chain: a.chain,
        reputation: a.reputation,
        totalCalls: a.totalCalls,
      })),
      timestamp: new Date().toISOString(),
    }
  }

  leaderboard() {
    return Array.from(this.agents.values())
      .sort((a, b) => b.reputation - a.reputation)
      .map((a, i) => ({
        rank: i + 1,
        name: a.name,
        reputation: a.reputation,
        calls: a.totalCalls,
        capabilities: a.capabilities,
      }))
  }
}

// ─── CLI ───────────────────────────────────────────────────────────
const args = process.argv.slice(2)
const registry = new AgentRegistry()

if (args.includes('--leaderboard')) {
  console.log('\n🏆 Agent Arena — OOBE Leaderboard\n')
  const board = registry.leaderboard()
  for (const entry of board) {
    console.log(`  #${entry.rank} ${entry.name} — Rep: ${entry.reputation} | Calls: ${entry.calls} | ${entry.capabilities.join(', ')}`)
  }
} else if (args.includes('--agent')) {
  const idx = args.indexOf('--agent')
  const name = args[idx + 1]
  const agent = registry.get(name)
  if (agent) {
    console.log(`\n🤖 ${agent.name}\n`)
    console.log(`  Description: ${agent.description}`)
    console.log(`  Chain: ${agent.chain}`)
    console.log(`  Capabilities: ${agent.capabilities.join(', ')}`)
    console.log(`  Pricing: ${agent.pricing.tier} (${agent.pricing.costPerCall} SOL/call, ${agent.pricing.dailyLimit}/day)`)
    console.log(`  Reputation: ${agent.reputation}`)
    console.log(`  Total Calls: ${agent.totalCalls}`)
  } else {
    console.log(`❌ Agent "${name}" not found. Available: ${Array.from(registry.agents.keys()).join(', ')}`)
  }
} else {
  const manifest = registry.manifest()
  console.log(JSON.stringify(manifest, null, 2))
}

export { AgentRegistry, CAPABILITIES, PRICING, AGENTS }
