# Link Relation Registration Draft

> **Historical preparation draft.** The [recorded submitted request](link-relation-registration-request.md)
> owns the filed wording. This draft is not current protocol status, a grant of
> change-control authority, or evidence of IANA approval. See [current status](../../README.md#status).

## Template Basis

RFC 8288 and IANA Link Relation Types Registry.

## Registration Request (Draft)

- Relation name: `pagedigest` (draft target)
- Description: identifies the pagedigest manifest for an origin.
- Reference: pagedigest v1 specification
- Notes:
  - During RC, URI-form extension relation remains valid:
    - `rel="https://pagedigest.org/rel"`
  - Target resource is usually `/.well-known/pagedigest.json`.

## Semantics Summary

- The relation identifies a change-detection manifest resource.
- Clients should treat relation identifiers as semantics labels, not dereference targets.
- Consumers may fetch the linked manifest and apply protocol rules for site/URL revision comparisons.

## Recorded submission and follow-up

- Request filed:
  [protocol-registries/link-relations#73](https://github.com/protocol-registries/link-relations/issues/73).
- Request text is tracked in
  [link-relation-registration-request.md](./link-relation-registration-request.md).
- Expert review may require a more stable or community-backed specification
  reference before permanent registration.
- Align final examples across README, SPEC, CONTRACT, and release checklist
  after registration.
