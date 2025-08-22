from enum import Enum

class WorkoutLoggingStates(Enum):
    SELECT_TYPE = 1
    SELECT_EXERCISE = 2
    LOG_SETS_REPS = 3
    LOG_WEIGHT = 4
    LOG_RPE = 5
    ADD_NOTES = 6
    LOG_DURATION = 7
    LOG_RATING = 8
    CONFIRMATION = 9