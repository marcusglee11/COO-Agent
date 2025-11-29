# Council Review Packet - Automatic Reminder

## 3 Ways to Ensure Review Packets Are Always Generated

### 1. **Use the Workflow Command** ✅ EASIEST
Whenever you complete a build/fix phase, just say:

```
/generate_review_packet
```

I'll automatically:
- Read the spec at `docs/Antigravity_Council_Review_Packet_Spec_v1.0.md`
- Generate the packet with all 7 sections
- Include flattened codebase
- Commit to `council_review/` directory

---

### 2. **Include in Task Completion**
When you see a phase is complete in `task.md`, remind me:

```
Phase X is complete - generate review packet
```

Or simply mention "review packet" when asking about completion.

---

### 3. **Set as a Rule** (Most Reliable)
Add this to your custom rules in Cursor settings:

**Rule**: "After completing any build/fix phase (R6.x, Phase X, etc.), always generate a Council Review Packet using /generate_review_packet before considering the work done."

---

## What Gets Generated

Every packet includes (per spec):
- **Section 0**: Metadata (phase, build ID, timestamp, scope)
- **Section 1**: Authority chain, files touched
- **Section 2**: Plan mapping (spec sections → code files)
- **Section 3**: Structural walkthrough
- **Section 4**: Tests, gates, determinism notes
- **Section 5**: AMU₀ changes, sandbox touchpoints
- **Section 6**: Complete flattened codebase
- **Section 7**: Open questions, implementer notes

**File**: `council_review/COO_Runtime_<PHASE>_Build_<SHA>_ReviewPacket_v1.0.txt`

---

## Current Workflow Status

✅ **Workflow file exists**: `.agent/workflows/generate_review_packet.md`  
✅ **Spec available**: `docs/Antigravity_Council_Review_Packet_Spec_v1.0.md`  
✅ **Generator exists**: `generate_r6_3_packet.py` (template for future phases)

---

## Example Usage

**You**: "R6.3 implementation complete"  
**Me**: *Generates walkthrough, updates task.md*  
**You**: "/generate_review_packet"  
**Me**: *Generates full Council Review Packet automatically*

---

## The Simplest Approach

Just make it part of your completion checklist:

1. ✅ Implementation complete
2. ✅ Tests pass (or documented why not)
3. ✅ Walkthrough written
4. ✅ **Review packet generated** ← `/generate_review_packet`
5. ✅ Ready for Council review
