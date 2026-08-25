-- Milestone 4: hypothesis evidence links and unanswered questions.

ALTER TABLE hypotheses
    ADD COLUMN IF NOT EXISTS supporting_evidence TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS contradicting_evidence TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS unanswered_questions TEXT[] DEFAULT '{}';
