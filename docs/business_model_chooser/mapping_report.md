# Business Model Chooser — Source→Template Mapping Report

> **v2 update (2026-07-19):** the converted workbook now uses **Import Template v2** —
> every main factor is a `Checkbox (multi-select)` whose 28 columns carry
> `Column Role = Value` with `Default Operator >=` / `Default Expected 60`
> (no 100% Split rule). The per-cell value mapping below is unchanged.

**Rules applied (locked with user 2026-07-19):**

- Unnamed sub-factor value → **0**
- Mentioned without `(X%)` → **100**
- Mentioned with `(X%)` → **X**

**Stats:** 10 main factors · 28 sub-factors · 54 patterns · 540 cells parsed · 1 legitimate N/A (BARTER · Differentiation Strategy).

---

## #1 — AFFILIATION

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo, Startup (40%) | **Solo**=100, **Startup**=40 |
| Solution Category | Products, Services (50%) | **Product**=100, **Service**=50 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium(70%), Low (40%) | **Low**=40, **Medium**=70 |
| Affordability | High | **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Multiple Points - Normal Solution (50%)  Single Point - Normal Solutio | **Single Point - Normal Solution**=70, **Single Point - Deeper Solution**=90, **Multiple Points - Normal Solution**=50 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #2 — AIKIDO

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startup ( 40%) SME (50%) | **Startup**=40, **SME**=50 |
| Solution Category | Products (50%) Services (50%) | **Product**=50, **Service**=50 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High(70%) Medium (40%) Low (20%) | **Low**=20, **Medium**=40, **High**=70 |
| Affordability | High (90%) Medium (40%) | **Medium**=40, **High**=90 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech (75%) Traditional (60%) | **Traditional**=60, **High Tech**=75 |
| Distribution Channels | Online - Direct          offline Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution (70%) Multiple point - Deeper Solution  | **Single Point - Deeper Solution**=70, **Multiple Points - Deeper Solution**=65 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #3 — AUCTION

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate Startups (30%) | **Startup**=30, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Pain Reliever, Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & Low | **Low**=100, **Medium**=100 |
| Affordability | Low & medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Multiple points - Normal Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #4 — BARTER

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo, Startups | **Solo**=100, **Startup**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct                    Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single Point - Normal Solution Single Point - Deeper Solution | **Single Point - Normal Solution**=100, **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Can't say, as transaction is not currency | _(all zero — N/A)_ |

## #5 — CASH MACHINE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startup(90%) SME (30%) | **Startup**=90, **SME**=30 |
| Solution Category | Prodcut (80%) Service (95%) | **Product**=80, **Service**=95 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High, Mediuim (70%), Low (30%) | **Low**=30, **Medium**=70, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech & Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct                 Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution (90%) Multiple point - Deeper Solution  | **Single Point - Deeper Solution**=90, **Multiple Points - Deeper Solution**=75 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #6 — CROSS SELLING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Product (90%) Service (85%) | **Product**=90, **Service**=85 |
| Nature of Solution | Pain Reliever & Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | High & Medium | **Medium**=100, **High**=100 |
| Affordability | High & Medium | **Medium**=100, **High**=100 |
| Revenue Model | B2C & B2B | **B2B**=100, **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Multiple point deeper Solutions | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven & Delivery Cost Driven | **Premium Value Driven**=100, **Delivery Cost Driven**=100 |

## #7 — CROWD-FUNDING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups & Solo | **Solo**=100, **Startup**=100 |
| Solution Category | Being a Platform | **Service**=100 |
| Nature of Solution | Gain Creator & Pain Reliever | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & Low | **Low**=100, **Medium**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution Multiple points - Normal Solution | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven & Premium Value Driver | **Premium Value Driven**=100, **Delivery Cost Driven**=100 |

## #8 — CROWD-SOURCING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups & Solo | **Solo**=100, **Startup**=100 |
| Solution Category | Being a Platform | **Service**=100 |
| Nature of Solution | Pain Reliever & Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | High & Medium | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution Multiple points - Normal Solution | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven & Premium Value Driver | **Premium Value Driven**=100, **Delivery Cost Driven**=100 |

## #9 — CUSTOMER LOYALTY

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Product & Service | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever & Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | High & Medium | **Medium**=100, **High**=100 |
| Affordability | High & Medium | **Medium**=100, **High**=100 |
| Revenue Model | B2C & B2B | **B2B**=100, **B2C**=100 |
| Tech Orientation | Tradotional & High Ticket | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct           Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Multiple point - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #10 — DIGITIZA-TION

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Pain Reliever & Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2B & B2C | **B2B**=100, **B2C**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct            Online - Channel | **Online - Direct**=100, **Online - Channel**=100 |
| Value Creation | Single Point - Deeper Solution Muliple Points - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Drivem, Premium Value Driven | **Premium Value Driven**=100 |

## #11 — DIRECT SELLING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startup & SME | **Startup**=100, **SME**=100 |
| Solution Category | Products & ServiceS | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever & Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | High & Medium | **Medium**=100, **High**=100 |
| Affordability | High & Medium | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech, Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct                 Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single Point - Norma Solution     Single Point - Deeper Solution Multi | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100, **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driver, Premium Value Driven | **Premium Value Driven**=100, **Delivery Cost Driven**=100 |

## #12 — E- COMMERCE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | StartUp & Solo | **Solo**=100, **Startup**=100 |
| Solution Category | Prodcut (80%) Service (95%) | **Product**=80, **Service**=95 |
| Nature of Solution | Pain Reliever & Gain Creator | **Pain Reliever**=100, **Gain Creator**=100 |
| Intensity/Urgency/Freq | High & Medium | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Normal Solution      Single Point - Deeper solution Mul | **Single Point - Normal Solution**=100, **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100, **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven  Premium Value Driven | **Premium Value Driven**=100, **Delivery Cost Driven**=100 |

## #13 — EXPERIENCE SELLING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | StartUp, SME & Corporate | **Startup**=100, **SME**=100, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | High & Medium | **Medium**=100, **High**=100 |
| Affordability | High | **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Offline - Direct        Offline - Channel | **Offline - Direct**=100, **Offline - Channel**=100 |
| Value Creation | Single Point - Deeper Solution        Multiple Points - Deeper Solutio | **Single Point - Deeper Solution**=100, **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #14 — FLAT RATE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo & StartUp | **Solo**=100, **Startup**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Low & Medium | **Low**=100, **Medium**=100 |
| Affordability | Medium & Low | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Oflline - Direct              Online - Direct | **Online - Direct**=100 |
| Value Creation | Multiple Points - Normal Solution           Single Point - Normal Solu | **Single Point - Normal Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #15 — FRAC-TIONALOWNERSHIP

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium & Low | **Low**=100, **Medium**=100 |
| Revenue Model | B2B & B2C | **B2B**=100, **B2C**=100 |
| Tech Orientation | Traditional with tech | **Traditional**=100 |
| Distribution Channels | offline - Direct, offline- Channel | **Offline - Direct**=100 |
| Value Creation | Single ponint - Normal Solution | **Single Point - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #16 — FRAN-CHISING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME, Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Product, Service | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional, High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct, offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Multiple Points - Normal Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #17 — FREEMIUM

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo, Startup | **Solo**=100, **Startup**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Hightech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution, Multiple point - Normal Solution | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #18 — FROM PUSH-TO-PULL

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Product, Service | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium and high | **Medium**=100, **High**=100 |
| Affordability | Low and Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2B, B2c, D2c | **B2B**=100, **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Online - channel, Online Direct | **Online - Direct**=100, **Online - Channel**=100 |
| Value Creation | Multiple points - Normal Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery cost Driven | **Delivery Cost Driven**=100 |

## #19 — GUARAN- TEED AVAIL- ABILITY

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate | **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium and High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Multiple points - Normal & Deeper Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #20 — HIDDEN REVENUE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startup & SME | **Startup**=100, **SME**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium and High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Hightech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #21 — INGREDIENT BRANDING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups | **Startup**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | High | **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Offline - Channel & Online - Channel | **Offline - Channel**=100, **Online - Channel**=100 |
| Value Creation | Single Point Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #22 — INTEGRATOR

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate | **Corporate**=100 |
| Solution Category | Product | **Product**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Single point - Deeper solution & Multiple points Normal Solution | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #23 — LAYER PLAYER

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups,SMEs & Corporate | **Startup**=100, **SME**=100, **Corporate**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Pain reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct & Offline _ Direct | **Online - Direct**=100 |
| Value Creation | Single Point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #24 — LEVERAGE CUSTOMER DATA

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups &SMEs | **Startup**=100, **SME**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Hightech | **High Tech**=100 |
| Distribution Channels | Online - Direct & Online - Channels | **Online - Direct**=100 |
| Value Creation | Single point - Deeper solution & Multiple points Normal Solution | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #25 — LICENSE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporates & SMEs | **SME**=100, **Corporate**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | medium | **Medium**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Single Ponint - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #26 — LOCK-IN

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SMEs & Startups | **Startup**=100, **SME**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Relievers | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct & Offline _ Direct | **Online - Direct**=100 |
| Value Creation | Multiple points - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #27 — LONG TAIL

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SMEs & Corporates | **SME**=100, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Multiple Points - Normal Soltuion | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #28 — MAKE MO-RE OF IT

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate & SME | **SME**=100, **Corporate**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Offline - Direct           Online - Direce | **Offline - Direct**=100 |
| Value Creation | Multiple Points - Normal Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #29 — MASS CUSTOM-IZATION

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate & SME | **SME**=100, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Low & medium | **Low**=100, **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct       Offline- Channel | **Offline - Direct**=100 |
| Value Creation | Single point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #30 — NO FRILLS

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups & SME | **Startup**=100, **SME**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Single point - Normal Solution | **Single Point - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #31 — OPEN BUSI- NESS MODEL

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate | **Corporate**=100 |
| Solution Category | Prodcut & Service | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C & B2B | **B2B**=100, **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Offline - Channel & Online - Channel | **Offline - Channel**=100, **Online - Channel**=100 |
| Value Creation | Multiple points - Normal Solution     Multiple Points - Deeper Solutio | **Multiple Points - Normal Solution**=100, **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #32 — OPEN SOURCE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startups & SME | **Startup**=100, **SME**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Pain Relievers | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Hightech & Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Channel | **Online - Channel**=100 |
| Value Creation | Multiple Points - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #33 — ORCHE-STRATOR

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B & B2C | **B2B**=100, **B2C**=100 |
| Tech Orientation | Hightech & Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Channel               Offline - Channel | **Offline - Channel**=100, **Online - Channel**=100 |
| Value Creation | Multiple points - Normal Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost driven | **Delivery Cost Driven**=100 |

## #34 — PAY PERUSE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo, Startup, SME & Corporate | **Solo**=100, **Startup**=100, **SME**=100, **Corporate**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B & B2C | **B2B**=100, **B2C**=100 |
| Tech Orientation | Hightech & Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct                 Online - Channel | **Online - Direct**=100, **Online - Channel**=100 |
| Value Creation | Multiple points - Normal Solution | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #35 — PAY WHAT YOU WANT

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo & StartUp | **Solo**=100, **Startup**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C & B2B | **B2B**=100, **B2C**=100 |
| Tech Orientation | Hightech & Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct                 Offline - Direct                       | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Multiple Points - Normal Soltuion | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #36 — PEER-TO- PEER

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startup & SMEs | **Startup**=100, **SME**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Hightech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #37 — PERFOR-MANCE- BASEDCONTRAC-TING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Product & Service | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Hightech, Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Offline - Direct           Online - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #38 — RAZOR ANDBLADE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Product | **Product**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Hightech, Traditional | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Offline - Direct             Online - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single Point - Deeper Solution        Multiple Points - Normal Solutio | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #39 — RENT INSTEAD OF BUY

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate & SME | **SME**=100, **Corporate**=100 |
| Solution Category | Product & Service | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | Low & medium | **Low**=100, **Medium**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional, High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct                 Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single point - Deeper Solution             Multiple Points - Normal So | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #40 — REVENUE SHARING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME | **SME**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Hightech | **High Tech**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single Point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #41 — REVERSE ENGINEER-ING

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME | **SME**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Single point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #42 — REVERSE INNOVATION

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Corporate | **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | High | **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Online - Direct             Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | SIngle point - Deeper solution  Multiple points - Normal Solution | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #43 — ROBIN HOOD

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Single point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #44 — SELF- SERVICE

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Single point - Deeper Solution             Multiple Points - Normal So | **Single Point - Deeper Solution**=100, **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #45 — SHOP-IN- SHOP

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creator | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Multiple Points - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #46 — SOLUTION PROVIDER

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME | **SME**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional, High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct             Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Multiple Points - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #47 — SUBSCRIPTION

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo, Startup, SME (35%), Corporate (10%) | **Solo**=100, **Startup**=100, **SME**=35, **Corporate**=10 |
| Solution Category | Service, Combo of Product & Service (35%) | **Product**=100, **Service**=35 |
| Nature of Solution | Pain Reliever (50%), Gain Creator (80%) | **Pain Reliever**=50, **Gain Creator**=80 |
| Intensity/Urgency/Freq | Low (35%), Medium (90%), High (5%) | **Low**=35, **Medium**=90, **High**=5 |
| Affordability | Low, Medium (50%) | **Low**=100, **Medium**=50 |
| Revenue Model | B2B (Preferred for more Profitability), B2C | **B2B**=100, **B2C**=100 |
| Tech Orientation | High Tech | **High Tech**=100 |
| Distribution Channels | Online - Direct, Online - Channel | **Online - Direct**=100, **Online - Channel**=100 |
| Value Creation | Multiple Points - Normal Solution  (Lock-in benefit due to multiple po | **Multiple Points - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #48 — SUPER MARKET

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium & High | **Medium**=100, **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct             online - Channel | **Online - Direct**=100, **Online - Channel**=100 |
| Value Creation | Multiple Points - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #49 — TARGET THEPOOR

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Solo, Startup & SME | **Solo**=100, **Startup**=100, **SME**=100 |
| Solution Category | Services & Products | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Reliever | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | High | **High**=100 |
| Affordability | Low & Medium | **Low**=100, **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single Point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #50 — TRASH-TO- CASH

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME | **SME**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Online - Direct | **Online - Direct**=100 |
| Value Creation | Single point - Normal Solution | **Single Point - Normal Solution**=100 |
| Differentiation Strategy | Delivery Cost Driven | **Delivery Cost Driven**=100 |

## #51 — TWO-SIDED MARKET

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | Startup & SME | **Startup**=100, **SME**=100 |
| Solution Category | Services | **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct               Offline - Direct                    Onli | **Offline - Direct**=100, **Online - Direct**=100, **Online - Channel**=100 |
| Value Creation | Multiple point - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #52 — ULTIMATELUXURY

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME & Corporate | **SME**=100, **Corporate**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | High | **High**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct                 Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single Pont - Deepere Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #53 — USER DE-SIGNED

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME | **SME**=100 |
| Solution Category | Products | **Product**=100 |
| Nature of Solution | Gain Creators | **Gain Creator**=100 |
| Intensity/Urgency/Freq | Medium | **Medium**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2C | **B2C**=100 |
| Tech Orientation | Traditional | **Traditional**=100 |
| Distribution Channels | Offline - Direct | **Offline - Direct**=100 |
| Value Creation | Multiple Point - Deeper Solution | **Multiple Points - Deeper Solution**=100 |
| Differentiation Strategy | Premium Value Driven | **Premium Value Driven**=100 |

## #54 — WHITE LABEL

| Main Factor | Source cell | → Sub-factor values |
|---|---|---|
| Org Type | SME | **SME**=100 |
| Solution Category | Products & Services | **Product**=100, **Service**=100 |
| Nature of Solution | Pain Relievers | **Pain Reliever**=100 |
| Intensity/Urgency/Freq | Medium & High | **Medium**=100, **High**=100 |
| Affordability | Medium | **Medium**=100 |
| Revenue Model | B2B | **B2B**=100 |
| Tech Orientation | Traditional & High Tech | **Traditional**=100, **High Tech**=100 |
| Distribution Channels | Online - Direct            Offline - Direct | **Offline - Direct**=100, **Online - Direct**=100 |
| Value Creation | Single Point - Deeper Solution | **Single Point - Deeper Solution**=100 |
| Differentiation Strategy | — | _(all zero — N/A)_ |
