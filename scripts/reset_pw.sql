-- Reset password for hkala8639@gmail.com to '12345678'
UPDATE users 
SET hashed_password='$2b$12$9KDkCq5XLTjZXak16ZSXgu72R.Rfpd9XpWAEciXrEcb9y1oye8gVK' 
WHERE email='hkala8639@gmail.com';

-- Show result
SELECT email, is_active FROM users;

