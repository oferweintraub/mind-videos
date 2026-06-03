# Public/Private Character Library — User Guide

## Overview

Characters can now be marked as **public** or **private**:
- **Public characters** appear in the shared library for all users to see and use
- **Private characters** are hidden from the library but still available to their creator

## Creating Characters

### Step 1: Fill in Character Details
- Enter the character description, style, voice settings, etc.
- Generate candidate images (3 options)

### Step 2: Select an Image
- Choose one of the generated candidate images
- After selection, a **visibility toggle** appears

### Step 3: Set Visibility
You'll see:
```
☑️  🌍 Public Character
This character will appear in the shared library for all users
```

Or if toggled to private:
```
☑️  🔒 Private Character
Only you can use this character
```

### Step 4: Save
- Click "Save Character"
- The character is saved with your chosen visibility setting

## Using Characters

### In Your Scripts
- Both public and private characters are available when creating scripts
- Use any character you have created, regardless of public/private status

### Sharing
- **Public characters** are automatically visible to other users in the library
- **Private characters** remain visible only to you
- Other users can still reference your public characters in their scripts

## API Reference

### GET /characters
List available characters.

**Query Parameters:**
- `public_only` (boolean, default=true) — If true, only return public characters

**Examples:**
```bash
# Get all public characters (default)
GET /characters

# Get all characters including private (admin/backend only)
GET /characters?public_only=false
```

**Response:**
```json
{
  "characters": [
    {
      "slug": "anchor_male",
      "display_name": "Male Anchor",
      "public": true,
      "image_url": "/static/characters/anchor_male/image.png",
      ...
    }
  ]
}
```

### POST /characters
Create a new character.

**Body:**
```json
{
  "slug": "my_character",
  "display_name": "My Character",
  "description": "Character description",
  "style": "lego",
  "public": true,
  "image_base64": "iVBORw0KGgo...",
  "voice": {
    "voice_id": "voice_123",
    "voice_name": "My Voice",
    "stability": 0.5,
    "similarity": 0.75,
    "style": 0.5,
    "tempo": 1.0
  }
}
```

### POST /characters/promote
Promote a candidate image to a full character.

**Body:**
```json
{
  "slug": "my_character",
  "idx": 1,
  "display_name": "My Character",
  "description": "Character description",
  "style": "lego",
  "public": false,  // or true for public
  "voice": { ... }
}
```

## Technical Details

### Character Data Structure
Each character's `manifest.json` now includes:
```json
{
  "slug": "anchor_male",
  "display_name": "Male Anchor",
  "description": "...",
  "style": "lego",
  "public": true,
  "voice": { ... },
  "image": "image.png"
}
```

### Backward Compatibility
- Existing characters without a `public` field automatically default to `public: true`
- No migration needed — existing library is preserved
- New characters default to `public: true` unless explicitly set otherwise

### Frontend Integration
The character editor (CastStep) now shows:
- A toggle switch for public/private visibility
- Clear indicator of current setting
- Help text explaining the implications

## Use Cases

### Scenario 1: Create a Reusable Character
1. Create a character with `public: true`
2. Other users see it in the library
3. Others can use it in their scripts
4. It becomes part of the shared character ecosystem

### Scenario 2: Create a Personal Character
1. Create a character with `public: false`
2. It doesn't appear in the library for others
3. You can still use it in your scripts
4. Change it to public later if you want to share it

### Scenario 3: Experiment Safely
1. Create experimental styles as `private` characters
2. Test them in your scripts
3. If they're good, change them to `public`
4. If not, delete them without cluttering the shared library

## Troubleshooting

### "My character isn't showing in the library"
- Check the visibility setting when you created it
- If it's set to private, only you can see it
- Change to public to make it visible to others

### "I can't find a character I created"
- It might be private — check your settings
- Use `GET /characters?public_only=false` (backend only) to see all
- Check the character directory: `server/characters/<slug>/manifest.json`

### "Existing characters disappeared"
- They're still there and set to `public: true`
- They load automatically on startup
- Clear browser cache if you're not seeing them in the UI

## Future Enhancements

Potential future features:
- Permission system (specific users can share)
- Character ratings/reviews from public library
- Bulk privacy changes
- Character groups/categories
- Search/filter by public/private status
