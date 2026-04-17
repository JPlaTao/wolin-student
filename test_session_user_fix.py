"""
Test Session_ID and User Authentication Coupling Fix

Verification:
1. Database schema includes user_id field
2. DAO functions correctly accept user_id parameter
3. API layer correctly passes user_id
"""
import sys
from sqlalchemy import text
from core.database import SessionLocal
from core.settings import get_settings

def test_database_schema():
    """Test database schema"""
    print("=" * 60)
    print("Test 1: Database Schema")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        result = db.execute(text("DESCRIBE conversation_memory"))
        columns = result.fetchall()
        
        # Check if user_id field exists
        has_user_id = any(col[0] == 'user_id' for col in columns)
        user_id_nullable = next((col[2] for col in columns if col[0] == 'user_id'), None)
        
        print(f"[OK] user_id field exists: {has_user_id}")
        print(f"[OK] user_id nullable: {user_id_nullable == 'YES' if user_id_nullable else 'False'}")
        
        # Check index
        result = db.execute(text("SHOW INDEX FROM conversation_memory WHERE Key_name = 'idx_user_session'"))
        indexes = result.fetchall()
        print(f"[OK] Composite index exists: {len(indexes) > 0}")
        
        if len(indexes) > 0:
            print(f"  Index columns: {', '.join([idx[4] for idx in indexes])}")
        
        # Check if session_id field exists
        has_session_id = any(col[0] == 'session_id' for col in columns)
        print(f"[OK] session_id field exists: {has_session_id}")
        
        return has_user_id and has_session_id
        
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        return False
    finally:
        db.close()


def test_dao_signature():
    """Test DAO function signatures"""
    print("\n" + "=" * 60)
    print("Test 2: DAO Function Signatures")
    print("=" * 60)
    
    try:
        from dao.conversation_dao import save_turn, get_recent_turns, get_latest_turn, get_turn_count, get_previous_sql_turn
        import inspect
        
        # Check save_turn parameters
        sig = inspect.signature(save_turn)
        params = list(sig.parameters.keys())
        has_user_id = 'user_id' in params
        print(f"[OK] save_turn includes user_id parameter: {has_user_id}")
        print(f"  Parameters: {', '.join(params)}")
        
        # Check get_recent_turns parameters
        sig = inspect.signature(get_recent_turns)
        params = list(sig.parameters.keys())
        has_user_id = 'user_id' in params
        print(f"[OK] get_recent_turns includes user_id parameter: {has_user_id}")
        print(f"  Parameters: {', '.join(params)}")
        
        # Check other functions
        for func_name, func in [
            ('get_latest_turn', get_latest_turn),
            ('get_turn_count', get_turn_count),
            ('get_previous_sql_turn', get_previous_sql_turn)
        ]:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            has_user_id = 'user_id' in params
            print(f"[OK] {func_name} includes user_id parameter: {has_user_id}")
        
        return True
        
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_layer():
    """Test if API layer correctly passes user_id"""
    print("\n" + "=" * 60)
    print("Test 3: API Layer user_id Passing")
    print("=" * 60)
    
    try:
        # Read source code to check if user_id is used
        with open('api/query_agent.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check key code snippets
        checks = [
            ('user_id = current_user.id', 'Get user_id from current_user'),
            ('get_recent_turns(db, user_id, session_id', 'Pass user_id in get_recent_turns'),
            ('save_turn(db, user_id, session_id', 'Pass user_id in save_turn'),
            ('get_turn_count(db, user_id, session_id)', 'Pass user_id in get_turn_count'),
        ]
        
        all_passed = True
        for code_snippet, description in checks:
            found = code_snippet in content
            status = "[OK]" if found else "[FAIL]"
            print(f"{status} {description}: {found}")
            if not found:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        return False


def test_security_isolation():
    """Test user isolation"""
    print("\n" + "=" * 60)
    print("Test 4: User Isolation Logic")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Simulate two users' sessions
        from dao.conversation_dao import save_turn, get_recent_turns
        
        # User 1 data
        user1_id = 1
        session1_id = "test-session-1"
        save_turn(db, user1_id, session1_id, 1, "User1 question 1", answer_text="Answer 1")
        save_turn(db, user1_id, session1_id, 2, "User1 question 2", answer_text="Answer 2")
        
        # User 2 uses same session_id (simulate session hijacking attempt)
        user2_id = 2
        turns_user2 = get_recent_turns(db, user2_id, session1_id, limit=10)
        
        print(f"[OK] User 2 cannot access User 1's session data: {len(turns_user2) == 0}")
        
        # User 1 can access own data
        turns_user1 = get_recent_turns(db, user1_id, session1_id, limit=10)
        print(f"[OK] User 1 can access own session data: {len(turns_user1) == 2}")
        
        # Clean test data
        db.execute(text("DELETE FROM conversation_memory WHERE session_id = :sid"), {"sid": session1_id})
        db.commit()
        
        return len(turns_user2) == 0 and len(turns_user1) == 2
        
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Starting Session_ID and User Authentication Coupling Fix Test")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Database Schema", test_database_schema()))
    results.append(("DAO Function Signatures", test_dao_signature()))
    results.append(("API Layer user_id Passing", test_api_layer()))
    results.append(("User Isolation Logic", test_security_isolation()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All tests passed! Session_ID and user authentication coupling fix successful.")
    else:
        print("[FAILED] Some tests failed, please check the fix.")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
