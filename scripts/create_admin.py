"""
Script to create an admin user.

This script creates an admin user in the database. It is intended to be run
manually after deployment to create the initial admin user.
"""
import argparse
import asyncio
import os
import sys
from typing import Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from api.core.config import settings
from api.core.security import get_password_hash
from api.db.sql import get_db, init_db
from api.models.user import User


async def create_admin_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    lang: str = "en-US",
) -> User:
    """
    Create an admin user.
    
    Args:
        email: User email
        password: User password
        display_name: User display name (defaults to email if not provided)
        lang: User language
        
    Returns:
        User: Created user
    """
    # Initialize database
    await init_db()
    
    # Get database session
    db = await anext(get_db())
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"User with email '{email}' already exists.")
        return existing_user
    
    # Create user
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        display_name=display_name or email.split("@")[0],
        lang=lang,
        is_active=True,
        is_verified=True,
        is_admin=True,  # Set admin flag
    )
    
    # Add to database
    db.add(user)
    db.commit()
    db.refresh(user)
    
    print(f"Admin user created: {user.email}")
    return user


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", type=str, required=True, help="User email")
    parser.add_argument("--password", type=str, required=True, help="User password")
    parser.add_argument("--display-name", type=str, help="User display name")
    parser.add_argument("--lang", type=str, default="en-US", help="User language")
    
    args = parser.parse_args()
    
    await create_admin_user(
        email=args.email,
        password=args.password,
        display_name=args.display_name,
        lang=args.lang,
    )


if __name__ == "__main__":
    asyncio.run(main())
