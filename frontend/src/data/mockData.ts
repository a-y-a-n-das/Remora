import type { Item } from '../types';

export const mockItems: Item[] = [
  {
    id: '1',
    name: 'Switzerland trip.jpg',
    type: 'image',
    date: 'Sep 17, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=500&q=80',
  },
  {
    id: '2',
    name: 'AWS bill ₹2,499.pdf',
    type: 'document',
    date: 'Sep 16, 2025',
  },
  {
    id: '3',
    name: 'OnePlus unboxing.jpg',
    type: 'image',
    date: 'Sep 15, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1585338447937-7082f8fc763d?w=500&q=80',
  },
  {
    id: '4',
    name: 'Project plan.jpg',
    type: 'image',
    date: 'Sep 14, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=500&q=80',
  },
  {
    id: '5',
    name: 'Flight to Delhi.jpg',
    type: 'image',
    date: 'Sep 12, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=500&q=80',
  },
  {
    id: '6',
    name: 'Code snippet.jpg',
    type: 'image',
    date: 'Sep 11, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=500&q=80',
  },
  {
    id: '7',
    name: 'HDFC statement.pdf',
    type: 'document',
    date: 'Sep 10, 2025',
  },
  {
    id: '8',
    name: 'Buddy.jpg',
    type: 'image',
    date: 'Sep 9, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1552053831-71594a27632d?w=500&q=80',
  },
  {
    id: '9',
    name: 'Trip - Europe.jpg',
    type: 'image',
    date: 'Sep 8, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=500&q=80',
  },
  {
    id: '10',
    name: 'Nature.jpg',
    type: 'image',
    date: 'Sep 7, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=500&q=80',
  },
  {
    id: '11',
    name: 'System design.jpg',
    type: 'image',
    date: 'Sep 6, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=500&q=80',
  },
  {
    id: '12',
    name: 'Headphones research.jpg',
    type: 'image',
    date: 'Sep 5, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80',
  },
  {
    id: '13',
    name: 'Goa trip.jpg',
    type: 'image',
    date: 'Sep 4, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=500&q=80',
  },
  {
    id: '14',
    name: 'App development.jpg',
    type: 'image',
    date: 'Sep 3, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1555099962-4199c345e5dd?w=500&q=80',
  },
  {
    id: '15',
    name: 'University notes.jpg',
    type: 'image',
    date: 'Sep 2, 2025',
    imageUrl:
      'https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=500&q=80',
  },
];

export const recentSearches = [
  'AWS bill ₹2,499',
  'OnePlus screenshots',
  'Flight tickets',
  'Laptop invoices',
  'Project images',
];

export const searchSuggestions = [
  'What did I spend on my recent purchases?',
  'What is the total amount on this receipt?',
  'When does my car insurance expire?',
  'What is my insurance policy number?',
  'What are the details of my upcoming trip?',
  'What is the booking or ticket number?',
  'What was the most recent payment I made?',
  'What are the important dates in my documents?',
  'Can you find my vehicle registration details?',
  'What did I buy recently?',
  'Find the details I need from my documents.',
];

export function makeSearchResults(query: string): Item[] {
  const q = query.toLowerCase();

  if (
    q.includes('aws') ||
    q.includes('bill') ||
    q.includes('invoice')
  ) {
    return [mockItems[1], mockItems[6]];
  }

  if (
    q.includes('flight') ||
    q.includes('delhi') ||
    q.includes('trip')
  ) {
    return [mockItems[4], mockItems[0], mockItems[8]];
  }

  if (
    q.includes('oneplus') ||
    q.includes('phone') ||
    q.includes('product')
  ) {
    return [mockItems[2], mockItems[11]];
  }

  if (
    q.includes('project') ||
    q.includes('plan') ||
    q.includes('design')
  ) {
    return [mockItems[3], mockItems[10]];
  }

  if (
    q.includes('laptop') ||
    q.includes('code') ||
    q.includes('dev')
  ) {
    return [mockItems[5], mockItems[13]];
  }

  return mockItems.slice(0, 4);
}

export function buildAssistantReply(query: string) {
  const results = makeSearchResults(query);

  return {
    id: Date.now().toString(),
    role: 'assistant' as const,
    content: `I found ${results.length} ${
      results.length === 1 ? 'item' : 'items'
    } in your collection that match "${query}".`,
    results,
    timestamp: new Date(),
  };
}