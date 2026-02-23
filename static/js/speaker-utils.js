/**
 * Speaker utility functions and constants
 */

// Speaker colors for transcript avatars
export const SPEAKER_COLORS = ['#3D8A5A', '#D89575', '#5B7DB1', '#A67BB5', '#6D6C6A'];

/**
 * Get initials from a name
 */
export function getInitials(name) {
    if (!name) return '?';
    return name.split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

/**
 * Get speaker color by index
 */
export function getSpeakerColor(index) {
    return SPEAKER_COLORS[index % SPEAKER_COLORS.length];
}
