from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date
import unittest.mock as mock

class TestLibraryBook(TransactionCase):
    def setUp(self):
        super(TestLibraryBook, self).setUp()
        # Create test data
        self.Book = self.env['library.book']
        self.Author = self.env['library.author']
        self.BorrowBook = self.env['library.borrow.book']
        self.Partner = self.env['res.partner']
        
        # Test author
        self.author = self.Author.create({
            'name': 'Test Author',
            'image': b'fake_image_data',  # Mock binary image
        })
        
        # Test member
        self.member = self.Partner.create({
            'name': 'Test Member',
            'image_1920': b'fake_member_image',
        })
        
        # Base book data
        self.book_vals = {
            'title': 'Test Book',
            'book_stock': 5,
            'author_id': self.author.id,
            'category': 'fiction',
        }

    # ----- Core CRUD Tests -----
    def test_book_creation(self):
        """Test basic book creation with defaults"""
        book = self.Book.create(self.book_vals)
        
        # Check defaults
        self.assertEqual(book.publication_date, date.today())
        self.assertEqual(book.user_id, self.env.user)
        self.assertEqual(book.states, 'available')
        self.assertEqual(book.nb_book_available, 5)  # No borrows yet

    # ----- Computed Field Tests -----
    def test_nb_book_available_computation(self):
        """Test _compute_nb_book_available"""
        book = self.Book.create(self.book_vals)
        
        # Create borrow records
        self.BorrowBook.create([
            {'book_id': book.id},  # Counts as 1 borrow
            {'book_id': book.id},  # Counts as 2 borrows
        ])
        
        book._compute_nb_book_available()
        self.assertEqual(book.nb_book_available, 3)  # 5 stock - 2 borrows

    # ----- Constraint Tests -----
    def test_state_available_constraint(self):
        """Test state_available_not_available constraint"""
        book = self.Book.create(self.book_vals)
        
        # Case 1: Available when nb_book_available > 0
        book.nb_book_available = 1
        book.state_available_not_available()
        self.assertEqual(book.states, 'available')
        
        # Case 2: Not available when nb_book_available = 0
        book.nb_book_available = 0
        book.state_available_not_available()
        self.assertEqual(book.states, 'not_available')

    # ----- Action Method Tests -----
    def test_action_open_authors(self):
        """Test action_open_authors returns correct window action"""
        book = self.Book.create(self.book_vals)
        action = book.action_open_authors()
        
        self.assertEqual(action['res_id'], self.author.id)
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertIn('form', str(action['views']))

    # ----- Security Vulnerability Tests -----
    def test_sql_injection_vulnerability(self):
        """Test search_books is vulnerable to SQL injection"""
        with self.assertRaises(Exception):
            # This should fail if SQL injection protection is added later
            self.Book.search_books("test'; DROP TABLE library_book; --")

    @mock.patch('odoo.sql_db.Cursor.execute')
    def test_hardcoded_password(self, mock_execute):
        """Test connect_to_external_db exposes hardcoded password"""
        password = self.Book.connect_to_external_db()
        self.assertEqual(password, 'SuperSecret123!')  # 😬

    # ----- Edge Cases -----
    def test_zero_stock(self):
        """Test behavior when book_stock = 0"""
        vals = self.book_vals.copy()
        vals['book_stock'] = 0
        book = self.Book.create(vals)
        
        self.assertEqual(book.states, 'not_available')
        self.assertEqual(book.nb_book_available, 0)

    def test_related_fields(self):
        """Test related fields (member_name, author_img, etc.)"""
        book = self.Book.create({
            **self.book_vals,
            'member_id': self.member.id,
        })
        
        self.assertEqual(book.member_name, 'Test Member')
        self.assertEqual(book.author_img, self.author.image)
        self.assertEqual(book.member_image, self.member.image_1920)

if __name__ == '__main__':
    unittest.main()