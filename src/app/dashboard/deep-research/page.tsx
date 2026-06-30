"use client";

import { useState } from "react";
import { QueryGenerator } from "@/components/chat/QueryGenerator";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { useConversations } from "@/context/ConversationContext";
import { useRouter } from "next/navigation";

export default function DeepResearchPage() {
  const [generatedQuery, setGeneratedQuery] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const { newConversation } = useConversations();
  const router = useRouter();

  const handleQueryGenerated = async (query: string) => {
    // Create a new conversation explicitly for deep research
    const newConv = newConversation();
    if (newConv) {
      setActiveConversationId(newConv.id);
      setGeneratedQuery(query);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#000000]">
      <div className="flex-1 overflow-y-auto">
        {!generatedQuery ? (
          <div className="min-h-full flex items-center justify-center p-4">
            <QueryGenerator onQueryGenerated={handleQueryGenerated} />
          </div>
        ) : (
          <div className="h-full">
            {activeConversationId && (
              <ChatInterface
                conversationId={activeConversationId}
                _deepResearch
                initialQuery={generatedQuery}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
